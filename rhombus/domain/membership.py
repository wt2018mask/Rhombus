"""Memory-bounded file membership-index primitives for Rhombus 2.0."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import heapq
import json
from pathlib import Path
import tempfile
from typing import Iterable, Iterator, TextIO


def _validate_sha256(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(f"{name} must be a 64-character SHA256 digest")
    int(value, 16)


def _validate_field(name: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must be non-empty")
    if any(char in value for char in "\t\r\n"):
        raise ValueError(f"{name} must not contain TSV control characters")


def _bucket(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:2]


@dataclass(frozen=True)
class MembershipIndexRecord:
    dataset_id: str
    record_id: str
    source_locator: str
    composition_key: str
    site_count: int
    structure_fingerprint_sha256: str
    prototype_group: str

    def __post_init__(self) -> None:
        for name, value in (
            ("dataset_id", self.dataset_id),
            ("record_id", self.record_id),
            ("source_locator", self.source_locator),
            ("composition_key", self.composition_key),
            ("prototype_group", self.prototype_group),
        ):
            _validate_field(name, value)
        if self.site_count <= 0:
            raise ValueError("site_count must be positive")
        _validate_sha256(
            "structure_fingerprint_sha256",
            self.structure_fingerprint_sha256,
        )


@dataclass(frozen=True)
class MembershipIndexSummary:
    dataset_id: str
    row_count: int
    source_file_sha256: str
    fingerprint_protocol_id: str
    prototype_group_protocol_id: str
    index_directory: str


def _write_sorted_chunks(
    rows: Iterable[str],
    work_dir: Path,
    stem: str,
    chunk_size: int,
) -> list[Path]:
    paths: list[Path] = []
    chunk: list[str] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= chunk_size:
            chunk.sort()
            path = work_dir / f"{stem}-{len(paths):06d}.chunk"
            path.write_text("".join(chunk), encoding="utf-8")
            paths.append(path)
            chunk.clear()
    if chunk:
        chunk.sort()
        path = work_dir / f"{stem}-{len(paths):06d}.chunk"
        path.write_text("".join(chunk), encoding="utf-8")
        paths.append(path)
    return paths


def _merge_chunks(paths: list[Path], output: Path) -> None:
    if not paths:
        output.write_text("", encoding="utf-8")
        return

    handles: list[TextIO] = [
        path.open("r", encoding="utf-8", newline="") for path in paths
    ]
    try:
        with output.open("w", encoding="utf-8", newline="") as target:
            for row in heapq.merge(*handles):
                target.write(row)
    finally:
        for handle in handles:
            handle.close()
        for path in paths:
            path.unlink(missing_ok=True)


def _validate_unique_second_field(path: Path, field_name: str) -> None:
    previous: str | None = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            value = parts[1]
            if value == previous:
                raise ValueError(f"duplicate {field_name}: {value}")
            previous = value


def _build_offsets(path: Path) -> dict[str, list[int]]:
    offsets: dict[str, list[int]] = {}
    with path.open("rb") as handle:
        previous_bucket: str | None = None
        while True:
            start = handle.tell()
            line = handle.readline()
            if not line:
                if previous_bucket is not None:
                    offsets[previous_bucket][1] = start
                break
            bucket = line.split(b"\t", 1)[0].decode("ascii")
            if bucket != previous_bucket:
                if previous_bucket is not None:
                    offsets[previous_bucket][1] = start
                offsets[bucket] = [start, -1]
                previous_bucket = bucket
    return offsets


def _spool_records(
    records: Iterable[MembershipIndexRecord],
    path: Path,
    *,
    dataset_id: str,
) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        for record in records:
            if record.dataset_id != dataset_id:
                raise ValueError(
                    "membership record dataset_id does not match index dataset_id"
                )
            handle.write(
                json.dumps(asdict(record), sort_keys=True, separators=(",", ":"))
                + "\n"
            )
            count += 1
    return count


def _iter_spool(path: Path) -> Iterator[MembershipIndexRecord]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield MembershipIndexRecord(**json.loads(line))


def build_membership_index(
    records: Iterable[MembershipIndexRecord],
    index_directory: str | Path,
    *,
    dataset_id: str,
    source_file_sha256: str,
    fingerprint_protocol_id: str,
    prototype_group_protocol_id: str,
    chunk_size: int = 100_000,
) -> MembershipIndexSummary:
    """Build an atomic, file-based index without materializing all records."""

    _validate_field("dataset_id", dataset_id)
    _validate_sha256("source_file_sha256", source_file_sha256)
    _validate_field("fingerprint_protocol_id", fingerprint_protocol_id)
    _validate_field("prototype_group_protocol_id", prototype_group_protocol_id)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    destination = Path(index_directory)
    if destination.exists():
        raise FileExistsError(f"membership index already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        dir=destination.parent,
        prefix=f".{destination.name}.building-",
    ) as temp_name:
        work = Path(temp_name)
        spool = work / "records.jsonl"
        row_count = _spool_records(records, spool, dataset_id=dataset_id)

        builders = {
            "record.tsv": lambda r: (
                f"{_bucket(r.record_id)}\t{r.record_id}\t{r.source_locator}\n"
            ),
            "exact.tsv": lambda r: (
                f"{r.structure_fingerprint_sha256[:2]}\t"
                f"{r.structure_fingerprint_sha256}\t{r.source_locator}\t"
                f"{r.record_id}\n"
            ),
            "near.tsv": lambda r: (
                f"{_bucket(f'{r.composition_key}|{r.site_count}')}\t"
                f"{r.composition_key}\t{r.site_count:09d}\t"
                f"{r.source_locator}\t{r.structure_fingerprint_sha256}\n"
            ),
            "prototype.tsv": lambda r: (
                f"{_bucket(r.prototype_group)}\t{r.prototype_group}\t"
                f"{r.source_locator}\t{r.structure_fingerprint_sha256}\n"
            ),
        }

        offsets: dict[str, dict[str, list[int]]] = {}
        for filename, formatter in builders.items():
            chunks = _write_sorted_chunks(
                (formatter(record) for record in _iter_spool(spool)),
                work,
                filename.replace(".tsv", ""),
                chunk_size,
            )
            output = work / filename
            _merge_chunks(chunks, output)
            if filename == "record.tsv":
                _validate_unique_second_field(output, "record_id")
            offsets[filename] = _build_offsets(output)

        spool.unlink(missing_ok=True)
        metadata = {
            "schema_version": "rhombus-membership-index-v1",
            "dataset_id": dataset_id,
            "row_count": row_count,
            "source_file_sha256": source_file_sha256,
            "fingerprint_protocol_id": fingerprint_protocol_id,
            "prototype_group_protocol_id": prototype_group_protocol_id,
            "files": {
                "record": "record.tsv",
                "exact": "exact.tsv",
                "near": "near.tsv",
                "prototype": "prototype.tsv",
            },
            "bucket_offsets": offsets,
        }
        (work / "metadata.json").write_text(
            json.dumps(metadata, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        Path(temp_name).replace(destination)

    return MembershipIndexSummary(
        dataset_id=dataset_id,
        row_count=row_count,
        source_file_sha256=source_file_sha256,
        fingerprint_protocol_id=fingerprint_protocol_id,
        prototype_group_protocol_id=prototype_group_protocol_id,
        index_directory=str(destination),
    )


def _iter_bucket_lines(
    index_directory: str | Path,
    filename: str,
    bucket: str,
) -> Iterator[str]:
    root = Path(index_directory)
    metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    bounds = metadata["bucket_offsets"][filename].get(bucket)
    if bounds is None:
        return
    start, end = bounds
    with (root / filename).open("rb") as handle:
        handle.seek(start)
        while handle.tell() < end:
            yield handle.readline().decode("utf-8").rstrip("\n")


def exact_membership_count(
    index_directory: str | Path,
    structure_fingerprint_sha256: str,
) -> int:
    _validate_sha256(
        "structure_fingerprint_sha256",
        structure_fingerprint_sha256,
    )
    count = 0
    bucket = structure_fingerprint_sha256[:2]
    for line in _iter_bucket_lines(index_directory, "exact.tsv", bucket):
        _, fingerprint, _, _ = line.split("\t", 3)
        if fingerprint == structure_fingerprint_sha256:
            count += 1
    return count


def candidate_locators_for_near_duplicate(
    index_directory: str | Path,
    *,
    composition_key: str,
    site_count: int,
) -> tuple[str, ...]:
    _validate_field("composition_key", composition_key)
    if site_count <= 0:
        raise ValueError("site_count must be positive")

    bucket = _bucket(f"{composition_key}|{site_count}")
    matches: list[str] = []
    for line in _iter_bucket_lines(index_directory, "near.tsv", bucket):
        _, composition, sites, locator, _ = line.split("\t", 4)
        if composition == composition_key and int(sites) == site_count:
            matches.append(locator)
    return tuple(sorted(matches))
