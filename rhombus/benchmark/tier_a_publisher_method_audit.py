"""Offline, source-only audit of the public LiTraj MACE-small NEB notebook.

This is a *protocol semantics* diagnostic, not an executable notebook runner,
benchmark freeze, model check, or authorization. It never evaluates notebook code,
opens trajectory/target files, imports ASE/MACE, or alters scientific evidence.
"""
from __future__ import annotations

import ast
from hashlib import sha1, sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "rhombus-0205-tier-a-publisher-notebook-method-audit-v1"
PUBLISHER_NOTEBOOK_REPO = "AIRI-Institute/LiTraj"
PUBLISHER_NOTEBOOK_RELATIVE_PATH = "notebooks/nebDFT2k_benchmark_MACE_MP_small.ipynb"
PUBLISHER_NOTEBOOK_COMMIT_OBSERVED = "c3ca5c2afbc13ffc823306f546dcee24486ade2a"
PUBLISHER_NOTEBOOK_GIT_BLOB_OBSERVED = "685f9628ccbe55daf2c717f791ab716e0a2806e7"
MAX_NOTEBOOK_BYTES = 2_000_000
MAX_CELLS = 200
MAX_CELL_CHARS = 100_000


def _literal(node: ast.AST) -> Any:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None
    return value if type(value) in (str, int, float, bool) else None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _named_calls(root: ast.AST, method: str) -> list[ast.Call]:
    return [item for item in ast.walk(root)
            if isinstance(item, ast.Call) and _call_name(item.func) == method]


def _named_keyword(call: ast.Call, keyword: str) -> Any:
    matches = [k.value for k in call.keywords if k.arg == keyword]
    return _literal(matches[0]) if len(matches) == 1 else None


def _call_binding(fn: ast.FunctionDef, call_kind: str, variable: str) -> ast.Call | None:
    matches: list[ast.Call] = []
    for node in fn.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if (isinstance(target, ast.Name) and target.id == variable
                    and isinstance(node.value, ast.Call)
                    and _call_name(node.value.func) == call_kind):
                matches.append(node.value)
    return matches[0] if len(matches) == 1 else None


def _run_call(fn: ast.FunctionDef, variable: str) -> dict[str, Any]:
    calls = [node for node in ast.walk(fn)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)
             and node.func.attr == "run"
             and isinstance(node.func.value, ast.Name)
             and node.func.value.id == variable]
    if len(calls) != 1:
        return {"observed_call_count": len(calls), "explicit_fmax": False,
                "explicit_steps": False, "fmax_value": None,
                "steps_value": None, "method_status": "MISSING_OR_AMBIGUOUS_RUN"}
    call = calls[0]
    names = [k.arg for k in call.keywords]
    if len(names) != len(set(names)) or any(x is None for x in names):
        raise ValueError("AMBIGUOUS_RUN_KEYWORDS")
    fmax = next((k.value for k in call.keywords if k.arg == "fmax"), None)
    steps = next((k.value for k in call.keywords if k.arg == "steps"), None)
    return {"observed_call_count": 1, "explicit_fmax": fmax is not None,
            "explicit_steps": steps is not None,
            "fmax_value": _literal(fmax) if fmax is not None else None,
            "steps_value": _literal(steps) if steps is not None else None,
            "method_status": "SOURCE_CALL_STATICALLY_OBSERVED"}


def audit_publisher_notebook_bytes(raw: bytes) -> dict[str, Any]:
    """Read JSON cell *source* only; outputs are never inspected or interpreted."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_NOTEBOOK_BYTES:
        raise ValueError("NOTEBOOK_BYTES_INVALID_OR_UNBOUNDED")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("INVALID_NOTEBOOK_JSON") from exc
    if type(document) is not dict or type(document.get("cells")) is not list:
        raise ValueError("INVALID_NOTEBOOK_SCHEMA")
    cells = document["cells"]
    if not 0 < len(cells) <= MAX_CELLS:
        raise ValueError("NOTEBOOK_CELL_COUNT_UNBOUNDED")
    optimize_functions: list[ast.FunctionDef] = []
    alias_calls: list[ast.Call] = []
    for cell in cells:
        if type(cell) is not dict or cell.get("cell_type") not in ("code", "markdown", "raw"):
            raise ValueError("INVALID_NOTEBOOK_CELL")
        if cell["cell_type"] != "code":
            continue
        source = cell.get("source")
        if type(source) is list and all(type(s) is str for s in source):
            code = "".join(source)
        elif type(source) is str:
            code = source
        else:
            raise ValueError("CODE_CELL_SOURCE_INVALID")
        if len(code) > MAX_CELL_CHARS:
            raise ValueError("CODE_CELL_TOO_LARGE")
        # Ignore plots and notebook outputs; only statically parse relevant cells.
        if "def optimize(" not in code and "mace_mp(" not in code:
            continue
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise ValueError("RELEVANT_SOURCE_NOT_PARSABLE") from exc
        optimize_functions.extend(node for node in tree.body
                                  if isinstance(node, ast.FunctionDef) and node.name == "optimize")
        alias_calls.extend(_named_calls(tree, "mace_mp"))
    if len(optimize_functions) != 1:
        raise ValueError("PUBLISHER_OPTIMIZE_FUNCTION_NOT_UNIQUE")
    fn = optimize_functions[0]
    defaults = dict(zip([a.arg for a in fn.args.args][-len(fn.args.defaults):],
                        [_literal(d) for d in fn.args.defaults])) if fn.args.defaults else {}
    if defaults.get("n_steps") != 100 or defaults.get("fmax") != 0.1:
        raise ValueError("PUBLISHER_OPTIMIZER_DEFAULTS_UNEXPECTED")
    neb_call = _call_binding(fn, "NEB", "neb")
    source_fire = _call_binding(fn, "FIRE", "qn_source")
    target_fire = _call_binding(fn, "FIRE", "qn_target")
    neb_fire = _call_binding(fn, "FIRE", "qn")
    if any(v is None for v in (neb_call, source_fire, target_fire, neb_fire)):
        raise ValueError("PUBLISHER_OPTIMIZER_CALLS_UNRESOLVED")
    neb = {"spring_eV_ang2": _named_keyword(neb_call, "k"),
           "climbing": _named_keyword(neb_call, "climb"),
           "method": _named_keyword(neb_call, "method"),
           "parallel": _named_keyword(neb_call, "parallel")}
    if neb != {"spring_eV_ang2": 5.0, "climbing": True,
               "method": "improvedtangent", "parallel": False}:
        raise ValueError("PUBLISHER_NEB_CALL_UNEXPECTED")
    alias = any(_named_keyword(call, "model") == "small"
                and _named_keyword(call, "default_dtype") == "float64"
                for call in alias_calls)
    if not alias:
        raise ValueError("PUBLISHER_SMALL_FLOAT64_ALIAS_NOT_OBSERVED")
    runs = {"source_endpoint": _run_call(fn, "qn_source"),
            "target_endpoint": _run_call(fn, "qn_target"),
            "neb": _run_call(fn, "qn")}
    if any(v["method_status"] != "SOURCE_CALL_STATICALLY_OBSERVED" for v in runs.values()):
        raise ValueError("PUBLISHER_RUN_CALL_UNRESOLVED")
    # AST Name n_steps/fmax is an argument reference, not a literal. Preserve
    # this crucial difference rather than infer a numeric convergence value.
    git_blob=sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()
    source_match=git_blob == PUBLISHER_NOTEBOOK_GIT_BLOB_OBSERVED
    return {
        "schema_version": SCHEMA,
        "notebook_sha256": sha256(raw).hexdigest(),
        "git_blob_sha1": git_blob,
        "matches_observed_public_git_blob": source_match,
        "source_identity": (
            "BYTES_MATCH_OBSERVED_PUBLIC_GIT_BLOB; NOT_RUNTIME_ATTESTATION"
            if source_match else "UNVERIFIED_LOCAL_SOURCE_NOT_OBSERVED_PUBLISHER_BLOB"
        ),
        "notebook_optimized_code_executed": False,
        "model_loaded_or_executed": False,
        "target_columns_or_trajectories_accessed": False,
        "source_function_defaults": defaults,
        "observed_mace_small_float64_alias": alias,
        "neb_construction": neb,
        "run_calls": runs,
        "semantic_discrepancies": [
            "SOURCE_ENDPOINT_FIRE_RUN_OMITS_EXPLICIT_FMAX_AND_STEPS",
            "NEB_FIRE_RUN_OMITS_EXPLICIT_FMAX",
            "TARGET_ENDPOINT_FIRE_RUN_ACCEPTS_NAMED_FMAX_AND_STEPS",
            "ASE_DEFAULTS_ARE_VERSION_DEPENDENT_UNLESS_EXPLICITLY_PINNED",
        ],
        "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN",
        "benchmark_status": "BENCHMARK_NOT_FROZEN",
        "execution_authorized": False,
    }


def compare_to_symmetric_tier_a_draft(audit: Mapping[str, Any],
                                      draft: Mapping[str, Any]) -> dict[str, Any]:
    """Do not promote similar physics into 'exact notebook reproduction'."""
    from .tier_a_budget_contract import inspect_budget_draft

    inspect_budget_draft(draft)
    if type(audit) is not dict or audit.get("schema_version") != SCHEMA:
        raise ValueError("PUBLISHER_METHOD_AUDIT_REQUIRED")
    if audit.get("execution_authorized") is not False or audit.get("benchmark_status") != "BENCHMARK_NOT_FROZEN":
        raise ValueError("UNAUTHORIZED_METHOD_PROMOTION")
    observed = audit.get("run_calls")
    if type(observed) is not dict or set(observed) != {"source_endpoint", "target_endpoint", "neb"}:
        raise ValueError("METHOD_OBSERVATION_MISSING")
    for key, status in observed.items():
        if type(status) is not dict or status.get("observed_call_count") != 1:
            raise ValueError("METHOD_OBSERVATION_INVALID")
    if not (observed["source_endpoint"]["explicit_fmax"] is False
            and observed["source_endpoint"]["explicit_steps"] is False
            and observed["target_endpoint"]["explicit_fmax"] is True
            and observed["target_endpoint"]["explicit_steps"] is True
            and observed["neb"]["explicit_fmax"] is False
            and observed["neb"]["explicit_steps"] is True):
        raise ValueError("PUBLISHER_METHOD_OBSERVATION_NOT_VERIFIED")
    return {"schema_version": "rhombus-0205-tier-a-method-comparability-v1",
            "publisher_note": "HISTORIC_PUBLIC_NOTEBOOK_STATIC_SOURCE_NOT_PUBLICATION_EXECUTION_RECEIPT",
            "choice_required": "EXACT_NOTEBOOK_SEMANTICS_VS_EXPLICIT_SHARED_BUDGET_NEB_METHOD",
            "symmetric_draft_not_exact_notebook_reproduction": True,
            "explicitly_pin_ase_default_behavior_before_exact_replication": True,
            "same_initial_paths_and_paired_fmax_necessary_not_sufficient": True,
            "neb_parameters_owner_frozen": False,
            "budget_owner_frozen": False,
            "execution_authorized": False,
            "scientific_status": "SCIENTIFIC_NO_GO_ABSTAIN"}


def read_notebook_file(path: Path) -> dict[str, Any]:
    """Explicit local source input only. Never fetch from URLs or execute cells."""
    import os
    import stat
    p = Path(path)
    if p.is_symlink() or not p.is_file():
        raise ValueError("NOTEBOOK_MUST_BE_REGULAR_LOCAL_FILE")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_NOTEBOOK_BYTES:
            raise ValueError("NOTEBOOK_SIZE_OR_FILE_TYPE_INVALID")
        raw = bytearray()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            while True:
                part = stream.read(min(65536, MAX_NOTEBOOK_BYTES + 1 - len(raw)))
                if not part:
                    break
                raw.extend(part)
                if len(raw) > MAX_NOTEBOOK_BYTES:
                    raise ValueError("NOTEBOOK_TOO_LARGE")
        after = os.fstat(fd)
        if (len(raw) != before.st_size or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns or before.st_ino != after.st_ino):
            raise ValueError("NOTEBOOK_CHANGED_DURING_READ")
        return audit_publisher_notebook_bytes(bytes(raw))
    finally:
        os.close(fd)
