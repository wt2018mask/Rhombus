"""Diagnostic, frame-at-a-time MPTrj nested JSON reader (Phase 3).

The Figshare source is a mapping of mp-id -> frame-id -> frame, each with
a serialized pymatgen Structure. Reading frames does NOT verify source hashes,
dataset coverage, or the exact MACE-MPA-0 training selection. Do not use
partially consumed generators or fixture parses to authorize training exposure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Callable, Iterator

import ijson
from ijson.common import ObjectBuilder
from pymatgen.core import Structure

from .membership import MembershipIndexRecord


class MPTrjFormatError(ValueError):
    """Invalid, duplicated, or unbounded nested MPTrj data."""


class _UniqueKeyDict(dict):
    """Refuse duplicate JSON keys, including nested frame/structure keys."""

    def __setitem__(self, key: str, value: object) -> None:
        if key in self:
            raise MPTrjFormatError("duplicate JSON member inside MPTrj frame")
        super().__setitem__(key, value)


@dataclass(frozen=True)
class MPTrjFrame:
    material_id: str
    frame_id: str
    source_locator: str
    structure: Structure


def _locator_component(component: str) -> str:
    return component.replace("~", "~0").replace("/", "~1")


def _require_id(value: object, kind: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MPTrjFormatError(f"{kind} must be a nonempty JSON key")
    if len(value) > 2048:
        raise MPTrjFormatError(f"{kind} exceeds bounded length")
    return value


def _next_event(events: Iterator[tuple[str, object]], context: str) -> tuple[str, object]:
    try:
        return next(events)
    except StopIteration as exc:
        raise MPTrjFormatError(f"truncated MPTrj JSON at {context}") from exc


def _read_frame(
    events: Iterator[tuple[str, object]],
    *,
    max_frame_events: int,
    max_frame_scalar_chars: int,
) -> dict:
    """Construct just one frame; enforce explicit event and scalar budgets."""
    builder = ObjectBuilder(map_type=_UniqueKeyDict)
    builder.event("start_map", None)
    depth = 1
    events_seen = 0
    scalar_chars = 0
    while depth:
        event, value = _next_event(events, "frame body")
        events_seen += 1
        if events_seen > max_frame_events:
            raise MPTrjFormatError("frame exceeds event budget")
        if event == "map_key" or event in ("string", "number", "integer", "double"):
            scalar_chars += len(str(value))
            if scalar_chars > max_frame_scalar_chars:
                raise MPTrjFormatError("frame exceeds scalar budget")
        if event in ("start_map", "start_array"):
            depth += 1
        elif event in ("end_map", "end_array"):
            depth -= 1
        builder.event(event, value)
    frame = builder.value
    if not isinstance(frame, dict):
        raise MPTrjFormatError("MPTrj frame is not an object")
    return frame


def _checked_events(source: BinaryIO) -> Iterator[tuple[str, object]]:
    """Normalize parser failures to an explicit scientific format error."""
    try:
        yield from ijson.basic_parse(
            source, use_float=True, multiple_values=False,
        )
    except (ijson.JSONError, UnicodeError, OverflowError) as exc:
        raise MPTrjFormatError("invalid or incomplete MPTrj JSON stream") from exc


def iter_mptrj_frames(
    source: BinaryIO,
    *,
    max_frame_events: int = 500_000,
    max_frame_scalar_chars: int = 8 * 1024 * 1024,
    max_material_keys: int = 250_000,
    max_frames_per_material: int = 250_000,
) -> Iterator[MPTrjFrame]:
    """Stream a single complete MPTrj root mapping; no file-level hash claims.

    Peak in-memory JSON is bounded to one frame and the capped ID sets, never
    the full ~12GB upstream mapping. This function must be consumed to EOF to
    check trailing garbage. Caller retains no authority from partial yields.
    """
    if min(
        max_frame_events, max_frame_scalar_chars,
        max_material_keys, max_frames_per_material,
    ) <= 0:
        raise ValueError("all parser resource limits must be positive")
    # YAJL C backend is the normal fast path; ijson also has a Python fallback.
    events = iter(_checked_events(source))
    event, _ = _next_event(events, "root")
    if event != "start_map":
        raise MPTrjFormatError("MPTrj root must be a mapping")
    material_ids: set[str] = set()
    yielded = 0
    for event, value in events:
        if event == "end_map":
            break
        if event != "map_key":
            raise MPTrjFormatError("unexpected root member event")
        material_id = _require_id(value, "material_id")
        if material_id in material_ids:
            raise MPTrjFormatError("duplicate material_id in MPTrj source")
        material_ids.add(material_id)
        if len(material_ids) > max_material_keys:
            raise MPTrjFormatError("material-ID set exceeds bounded limit")
        event, _ = _next_event(events, "material frames")
        if event != "start_map":
            raise MPTrjFormatError("material frames must be an object")
        frame_ids: set[str] = set()
        for event, value in events:
            if event == "end_map":
                break
            if event != "map_key":
                raise MPTrjFormatError("unexpected material frame event")
            frame_id = _require_id(value, "frame_id")
            if frame_id in frame_ids:
                raise MPTrjFormatError("duplicate frame_id in MPTrj material")
            frame_ids.add(frame_id)
            if len(frame_ids) > max_frames_per_material:
                raise MPTrjFormatError("frame-ID set exceeds bounded limit")
            event, _ = _next_event(events, "frame object")
            if event != "start_map":
                raise MPTrjFormatError("frame must be an object")
            frame = _read_frame(
                events,
                max_frame_events=max_frame_events,
                max_frame_scalar_chars=max_frame_scalar_chars,
            )
            serialized = frame.get("structure")
            if not isinstance(serialized, dict):
                raise MPTrjFormatError("frame missing pymatgen Structure object")
            try:
                structure = Structure.from_dict(serialized)
            except (TypeError, ValueError, KeyError, AttributeError) as exc:
                raise MPTrjFormatError("invalid pymatgen Structure in frame") from exc
            if len(structure) <= 0:
                raise MPTrjFormatError("empty MPTrj structure")
            locator = "/" + "/".join(
                (_locator_component(material_id), _locator_component(frame_id))
            )
            yielded += 1
            yield MPTrjFrame(material_id, frame_id, locator, structure)
        else:
            raise MPTrjFormatError("truncated MPTrj material mapping")
    else:
        raise MPTrjFormatError("truncated MPTrj root mapping")
    if yielded == 0:
        raise MPTrjFormatError("MPTrj source contains no frames")
    # Drain to detect unexpected additional top-level data if parser returns
    # events; ijson itself also validates trailing bytes on full consumption.
    if next(events, None) is not None:
        raise MPTrjFormatError("unexpected content after MPTrj root")


def iter_mptrj_membership_records(
    source: BinaryIO,
    *,
    fingerprint: Callable[[Structure], str],
    prototype_group: Callable[[Structure], str],
    max_frame_events: int = 500_000,
    max_frame_scalar_chars: int = 8 * 1024 * 1024,
) -> Iterator[MembershipIndexRecord]:
    """Produce diagnostic membership records, NOT a production audit index.

    Exact-match inference still requires frozen strict structure comparators.
    These records are NOT training-source attestations.
    """
    for frame in iter_mptrj_frames(
        source,
        max_frame_events=max_frame_events,
        max_frame_scalar_chars=max_frame_scalar_chars,
    ):
        yield MembershipIndexRecord(
            dataset_id="MPTrj",
            record_id=frame.source_locator,
            source_locator=frame.source_locator,
            composition_key=frame.structure.composition.element_composition.reduced_formula,
            site_count=len(frame.structure),
            structure_fingerprint_sha256=fingerprint(frame.structure),
            prototype_group=prototype_group(frame.structure),
        )
