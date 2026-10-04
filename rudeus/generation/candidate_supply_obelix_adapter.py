"""Read-only adapter from a supplied OBELiX checkout to explicit source evidence."""

from __future__ import annotations

import copy
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PureWindowsPath
import subprocess


_ADAPTER_SCHEMA = "candidate-supply-v2-obelix-adapter-v1"
_RESERVED_ROW_FIELDS = {"source_id", "structure_ref"}


@dataclass
class ObelixAdapterResult:
    source_rows: list
    source_snapshot: dict
    cif_inventory: list
    structure_provider: object
    adapter_provenance: dict


def _mapping(value, label):
    from collections.abc import Mapping

    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a mapping")
    return value


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _relative_path(value, label):
    text = _text(value, label)
    posix_path = Path(text)
    windows_path = PureWindowsPath(text)
    if posix_path.is_absolute() or windows_path.is_absolute():
        raise ValueError(f"{label} must be root-relative")
    if ".." in posix_path.parts or ".." in windows_path.parts:
        raise ValueError(f"{label} must not escape the checkout")
    return posix_path


def _git(root, *args):
    environment = dict(os.environ)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            shell=False,
        )
    except OSError as exc:
        raise ValueError("unable to inspect supplied checkout Git metadata") from exc
    if result.returncode != 0:
        raise ValueError("supplied root is not a valid Git checkout")
    return result.stdout.strip()


def _git_identity(root):
    top = Path(_git(root, "rev-parse", "--show-toplevel")).resolve()
    if top != root:
        raise ValueError("supplied root must be the Git checkout root")
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError("supplied Git checkout must be clean")
    commit = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    tree = _git(root, "rev-parse", "--verify", "HEAD^{tree}")
    if not commit or not tree:
        raise ValueError("Git commit and tree identities are required")
    return commit, tree


def _canonical_json_sha256(value):
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("adapter identity must be finite JSON data") from exc
    return hashlib.sha256(payload).hexdigest()


def _read_csv(csv_path, config):
    raw_bytes = csv_path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("processed.csv must be UTF-8 text") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = reader.fieldnames
    if not headers or any(not isinstance(name, str) or not name.strip() for name in headers):
        raise ValueError("processed.csv must have a valid header")
    if len(headers) != len(set(headers)):
        raise ValueError("processed.csv contains duplicate column names")
    id_column = config["id_column"]
    if id_column not in headers:
        raise ValueError(f"processed.csv is missing required ID column {id_column!r}")
    if _RESERVED_ROW_FIELDS.intersection(headers):
        raise ValueError("processed.csv uses reserved adapter output column names")
    required = config["required_selection_columns"]
    missing = [name for name in required if name not in headers]
    if missing:
        raise ValueError(f"processed.csv is missing configured selection columns: {missing}")

    rows_by_id = {}
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"processed.csv row {row_number} has extra fields")
        raw_id = row.get(id_column)
        if not isinstance(raw_id, str) or not raw_id.strip() or raw_id != raw_id.strip():
            raise ValueError(f"processed.csv row {row_number} has an invalid ID")
        if raw_id in rows_by_id:
            raise ValueError(f"processed.csv contains duplicate ID {raw_id!r}")
        rows_by_id[raw_id] = row
    if not rows_by_id:
        raise ValueError("processed.csv must contain at least one source row")
    return raw_bytes, rows_by_id


def _scan_cifs(root, cif_dir, rows_by_id):
    if not cif_dir.is_dir():
        raise ValueError("configured CIF directory is missing")
    paths_by_id = {}
    for candidate in cif_dir.rglob("*"):
        if candidate.is_symlink():
            raise ValueError("CIF inventory does not allow symlinks")
        if not candidate.is_file() or candidate.suffix.lower() != ".cif":
            continue
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("CIF path escapes supplied checkout") from exc
        source_id = candidate.stem
        paths_by_id.setdefault(source_id, []).append((relative, candidate))

    for source_id, matches in paths_by_id.items():
        if len(matches) != 1:
            raise ValueError(f"multiple CIF files resolve to source ID {source_id!r}")

    inventory = []
    linked_paths = {}
    for source_id in sorted(set(rows_by_id).union(paths_by_id)):
        matches = paths_by_id.get(source_id, [])
        if matches:
            relative, path = matches[0]
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            linked_paths[source_id] = path
            inventory.append({
                "source_id": source_id,
                "source_row_present": source_id in rows_by_id,
                "relative_path": relative,
                "cif_present": True,
                "content_sha256": content_hash,
            })
        else:
            inventory.append({
                "source_id": source_id,
                "source_row_present": True,
                "relative_path": None,
                "cif_present": False,
                "content_sha256": None,
            })
    return inventory, linked_paths


def _adapter_config(adapter_config):
    config = copy.deepcopy(dict(_mapping(adapter_config, "adapter_config")))
    for field in (
        "source_name", "source_namespace", "source_schema_version",
        "source_artifact_id", "processed_csv_relative_path",
        "cif_dir_relative_path", "id_column",
    ):
        _text(config.get(field), f"adapter_config.{field}")
    required = config.get("required_selection_columns")
    if not isinstance(required, list) or any(
        not isinstance(name, str) or not name.strip() for name in required
    ):
        raise ValueError("required_selection_columns must be an explicit string list")
    if len(required) != len(set(required)):
        raise ValueError("required_selection_columns contains duplicates")
    identity = _mapping(
        config.get("adapter_config_identity"), "adapter_config_identity"
    )
    _text(identity.get("schema_version"), "adapter_config_identity.schema_version")
    _text(identity.get("content_sha256"), "adapter_config_identity.content_sha256")
    return config


def build_candidate_supply_v2_obelix_adapter(
    obelix_root,
    *,
    adapter_config,
    parser,
):
    """Adapt one clean local OBELiX checkout without parsing until provider use."""
    if obelix_root is None or not str(obelix_root).strip():
        raise ValueError("obelix_root must be explicitly supplied")
    supplied_root = Path(obelix_root)
    if not supplied_root.is_absolute() and not PureWindowsPath(str(obelix_root)).is_absolute():
        raise ValueError("obelix_root must be an explicit absolute checkout path")
    root = supplied_root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("obelix_root must be a directory")
    config = _adapter_config(adapter_config)
    if not callable(parser):
        raise ValueError("parser must be callable")
    commit, tree = _git_identity(root)

    csv_relative = _relative_path(
        config["processed_csv_relative_path"], "processed_csv_relative_path"
    )
    cif_relative = _relative_path(
        config["cif_dir_relative_path"], "cif_dir_relative_path"
    )
    csv_path = (root / csv_relative).resolve(strict=True)
    cif_dir = (root / cif_relative).resolve(strict=True)
    for target in (csv_path, cif_dir):
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("configured source path escapes supplied checkout") from exc
    if not csv_path.is_file():
        raise ValueError("processed.csv is missing")
    raw_csv, rows_by_id = _read_csv(csv_path, config)
    inventory, linked_paths = _scan_cifs(root, cif_dir, rows_by_id)
    inventory_digest = _canonical_json_sha256(inventory)

    source_rows = []
    for source_id in sorted(rows_by_id):
        row = copy.deepcopy(rows_by_id[source_id])
        row["source_id"] = source_id
        row["structure_ref"] = (
            linked_paths[source_id].relative_to(root).as_posix()
            if source_id in linked_paths else None
        )
        source_rows.append(row)

    def structure_provider(parent_id):
        if not isinstance(parent_id, str):
            raise ValueError("provider identity must be a canonical string")
        prefix = f"{config['source_namespace']}:"
        if not parent_id.startswith(prefix) or not parent_id[len(prefix):]:
            raise KeyError(f"unknown parent identity: {parent_id!r}")
        source_id = parent_id[len(prefix):]
        if source_id not in rows_by_id:
            raise KeyError(f"unknown parent identity: {parent_id!r}")
        cif_path = linked_paths.get(source_id)
        if cif_path is None:
            return None
        return parser(cif_path)

    source_data_identity = {
        "processed_csv_sha256": hashlib.sha256(raw_csv).hexdigest(),
        "cif_inventory_sha256": inventory_digest,
        "processed_csv_relative_path": csv_relative.as_posix(),
        "cif_dir_relative_path": cif_relative.as_posix(),
    }
    snapshot = {
        "source_name": config["source_name"],
        "source_dataset": config["source_namespace"],
        "source_schema_version": config["source_schema_version"],
        "source_artifact_id": config["source_artifact_id"],
        "source_repository_commit": commit,
        "source_repository_tree": tree,
        "adapter_schema_version": _ADAPTER_SCHEMA,
        "adapter_config_identity": copy.deepcopy(config["adapter_config_identity"]),
        "source_data_identity": source_data_identity,
    }
    provenance = {
        "schema_version": _ADAPTER_SCHEMA,
        "adapter_config": copy.deepcopy(config),
        "cif_inventory_count": len(inventory),
        "orphan_cif_source_ids": [
            item["source_id"] for item in inventory
            if item["cif_present"] and not item["source_row_present"]
        ],
    }
    return ObelixAdapterResult(
        source_rows=source_rows,
        source_snapshot=copy.deepcopy(snapshot),
        cif_inventory=copy.deepcopy(inventory),
        structure_provider=structure_provider,
        adapter_provenance=provenance,
    )
