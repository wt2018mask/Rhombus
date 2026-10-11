"""0142: scientific prospective MATERIAL-level precision feasibility, not approval.

A Wilson half-width is mathematically defensible only for independent sampled
material-level Bernoulli outcomes and an appropriate sampling frame. Source
rows, independent-looking trajectories and per-class quota samples do NOT
establish these assumptions. This module never sees a real sealed roster.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist

SCHEMA = "rhombus-prospective-independent-material-precision-0142-v1"
REPORT_SCHEMA = "rhombus-prospective-material-feasibility-0142-v1"
IID_DESIGN = "PROSPECTIVE_IID_INDEPENDENT_MATERIALS_ASSUMED"
NONIID_DESIGN = "QUOTA_CLUSTERED_OR_INDEPENDENCE_UNVERIFIED"
UNIT = "UNIQUE_INDEPENDENT_MATERIAL_NOT_TRAJECTORY"
COHORT = "NEW_EXTERNALLY_STEWARD_SEALED_COHORT"
ENDPOINT = "ALL_PREREGISTERED_MATERIALS_INCLUDING_FAILED_UNKNOWN_AND_ABSTAINED"
MAX_SAMPLE_TARGET = 100_000
MAX_JSON_BYTES = 16_384
FIELDS = frozenset({
    "schema_version", "unit", "cohort_source", "sampling_design", "endpoint",
    "confidence_level", "maximum_wilson_half_width",
    "prospective_pre_enrollment_nonacquisition_fraction",
    "post_enrollment_failures_count_in_denominator",
})


def _finite_number(value, lower, upper, name, *, upper_inclusive=True):
    if type(value) not in (float, int):
        raise ValueError("invalid " + name)
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("invalid " + name)
    if value < lower or (value >= upper if not upper_inclusive else value > upper):
        raise ValueError("out-of-range " + name)
    return float(value)


def _maximum_wilson_half_width(n: int, z: float) -> float:
    if type(n) is not int or n < 1:
        raise ValueError("number of independent materials must be positive integer")
    return z / (2 * math.sqrt(n + z * z))


def _minimum_iid_materials(confidence: float, half_width: float) -> tuple[int, float]:
    z = NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    if not math.isfinite(z) or z <= 0:
        raise ValueError("unsupported Wilson critical value")
    requested = z * z / (4 * half_width * half_width) - z * z
    if not math.isfinite(requested) or requested > MAX_SAMPLE_TARGET:
        raise ValueError("IID precision target beyond supported material budget")
    n = max(1, math.ceil(requested))
    # Numerically guard the ceiling against floating-point boundary error.
    while _maximum_wilson_half_width(n, z) > half_width:
        n += 1
    while n > 1 and _maximum_wilson_half_width(n - 1, z) <= half_width:
        n -= 1
    if n > MAX_SAMPLE_TARGET:
        raise ValueError("unsupported material target")
    return n, _maximum_wilson_half_width(n, z)


def plan_independent_material_study(request: dict) -> dict:
    if not isinstance(request, dict) or set(request) != FIELDS:
        raise ValueError("unsupported prospective preregistration schema")
    if (request["schema_version"] != SCHEMA or request["unit"] != UNIT
        or request["cohort_source"] != COHORT or request["endpoint"] != ENDPOINT
        or request["sampling_design"] not in (IID_DESIGN, NONIID_DESIGN)
        or request["post_enrollment_failures_count_in_denominator"] is not True):
        raise ValueError("unsupported study unit, prospective source or outcome policy")
    confidence = _finite_number(
        request["confidence_level"], 0.8, 0.99, "confidence level")
    width = _finite_number(
        request["maximum_wilson_half_width"], 0.01, 0.25,
        "Wilson half-width", upper_inclusive=False)
    nonacquisition = _finite_number(
        request["prospective_pre_enrollment_nonacquisition_fraction"],
        0.0, 0.5, "pre-enrollment nonacquisition fraction",
    )
    iid = request["sampling_design"] == IID_DESIGN
    n = None
    upper = None
    recruited = None
    if iid:
        n, upper = _minimum_iid_materials(confidence, width)
        recruited = math.ceil(n / (1.0 - nonacquisition))
        # Rounding cannot silently grant a smaller-than-required roster.
        while recruited * (1.0 - nonacquisition) < n:
            recruited += 1
        if recruited > MAX_SAMPLE_TARGET:
            raise ValueError("prospective recruitment budget unsupported")
    return {
        "schema_version": REPORT_SCHEMA,
        "validated_prospective_plan_sha256": hashlib.sha256(
            json.dumps(request, allow_nan=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest(),
        "sampling_design": request["sampling_design"],
        "statistical_precision_method": (
            "WILSON_WORST_CASE_HALF_WIDTH_CONDITIONAL_ON_IID"
            if iid else "NOT_DEFENSIBLE_FOR_NON_IID"),
        "iid_is_only_a_preregistered_assumption_NOT_attested": iid,
        "independent_materials_needed_if_IID": n,
        "worst_case_Wilson_half_width_if_IID": upper,
        "prospective_minimum_recruitment_if_IID": recruited,
        "anticipated_pre_enrollment_nonacquisition_fraction": nonacquisition,
        "confidence_level": confidence,
        "target_maximum_half_width": width,
        "precision_target_only_NOT_statistical_power": True,
        "precision_for_subgroups_or_strata_not_established": True,
        "post_enrollment_model_failures_abstentions_unknowns_count_as_outcomes": True,
        "repeated_trajectories_or_source_rows_not_independent_materials": True,
        "public_OBELiX_TEST_and_old_B3_not_new_blind_materials": True,
        "real_external_blind_material_roster_supplied": False,
        "actual_independent_material_sample_count_authenticated": None,
        "external_steward_authentication_present": False,
        "recruitment_target_achieved": False,
        "actual_precision_empirically_observed": False,
        "new_materials_scientifically_qualified": 0,
        "P0_01_status": "BLOCKED",
        "P0_02_status": "BLOCKED",
        "P0_03_status": "BLOCKED",
        "scientific_release_authorized": False,
        "plan_status": "PLAN_ONLY_NOT_EVIDENCE" if iid else "BLOCKED_NON_IID",
    }


def _strict_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate prospective plan field")
        result[key] = value
    return result


def _no_constant(value):
    raise ValueError("nonfinite literal in prospective plan")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-plan-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.study_plan_json.is_symlink():
            raise ValueError("symlink study plan is not permitted")
        source = args.study_plan_json.resolve(strict=True)
        output = args.output_dir.resolve()
        if not source.is_file() or output.exists() or (
            output == source or source in output.parents
        ):
            raise ValueError("study plan must be regular file, output must be new")
        with source.open("rb") as handle:
            data = handle.read(MAX_JSON_BYTES + 1)
        if not data or len(data) > MAX_JSON_BYTES:
            raise ValueError("prospective plan exceeds byte budget")
        plan = json.loads(
            data, object_pairs_hook=_strict_keys, parse_constant=_no_constant,
        )
        report = plan_independent_material_study(plan)
        output.mkdir(parents=True, exist_ok=False)
        (output / "prospective_material_feasibility.json").write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8")
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
