"""Frozen S1 prospective isotropic-Brownian calibration plan content.

Single frozen scientific contract: analytic ensemble diffusion truth for an
isotropic Brownian generator, disjoint DEV/HELD_OUT seeds, one frozen
estimator configuration. Descriptive diagnostics only; no qualification,
no PASS/FAIL, no acceptance verdict.

This module is the canonical home of the S1 frozen content (previously
defined in tests). Values here are committed scientific content: do not
alter them without a new frozen contract.
"""
import numpy as np

from rudeus.science.calibration import (
    CalibrationClass,
    CalibrationDatasetManifest,
    CalibrationPlan,
    CalibrationScope,
    GeneratorSpec,
    SplitAssignment,
    TruthRecord,
    TruthType,
)
from rudeus.science.contracts import digest

# Frozen S1 scientific content ------------------------------------------------
S1_DIFFUSION_TENSOR_A2_PER_PS = 0.1
S1_TRUTH_D_M2_PER_S = 1.0e-9  # 0.1 A^2/ps ensemble mean; 1 A^2/ps == 1e-8 m^2/s
S1_DEV_SEEDS = {"s1-dev-1": 11, "s1-dev-2": 12}
S1_HELDOUT_SEEDS = {"s1-held-1": 21, "s1-held-2": 22}
S1_ESTIMATOR_CONFIG = {
    "lag_steps": [1, 2],
    "fit_window_ps": [0.5, 2.5],
    "selected_species": ["Li"],
    "volume_A3": 1000.0,
    "temperature_K": 550.0,
    "reference_frame": "simulation_cell",
}
S1_CODE_REVISION = "f" * 40


def _h(*parts):
    return digest({"s1": list(parts)})


def build_s1_plan_family(store):
    """Author and persist the frozen S1 plan artifact family. Returns hashes."""
    scope = CalibrationScope(
        estimator="free_intercept_OLS_MSD", estimator_version="v1",
        resampling_method="m", resampling_version="2", protocol_hash=_h("protocol"),
        estimand="D_self", units="m2/s",
        generator_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_version="gv",
        truth_type=TruthType.ANALYTICAL, truth_model_version="brownian-analytic-v1",
        species_composition={"Li": 2}, n_particles=2,
        duration_ps=8.0, sampling_interval_ps=1.0, lag_steps=(1, 2),
        code_revision=S1_CODE_REVISION)
    scope_h = store.store(scope)
    truth_h = store.store(TruthRecord(
        estimand="D_self", units="m2/s", truth_type=TruthType.ANALYTICAL,
        value={"D_m2_per_s": S1_TRUTH_D_M2_PER_S},
        statistical_interpretation="ensemble",
        window_interpretation="long_time",
        cell_interpretation="bulk",
        code_revision=S1_CODE_REVISION))
    gen_h = store.store(GeneratorSpec(
        calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN, generator_name="brownian",
        generator_version="synthetic-v1",
        parameters={"n_frames": 8, "n_ions": 2,
                    "diffusion_tensor": (S1_DIFFUSION_TENSOR_A2_PER_PS * np.eye(3)).tolist(),
                    "dt_ps": 1.0},
        initialization_spec={}, seed_semantics="pcg64",
        output_coordinate_contract={}, code_hash=_h("code")))
    plan_h = store.store(CalibrationPlan(
        objective="s1-isotropic-brownian-prospective",
        scope_hashes=(scope_h,),
        class_inventory=(CalibrationClass.ISOTROPIC_BROWNIAN,),
        parameter_cell_ids=("cell-a",), truth_requirements={},
        split_rules={}, seed_policy={},
        dev_replicate_ids=tuple(S1_DEV_SEEDS),
        heldout_replicate_ids=tuple(S1_HELDOUT_SEEDS),
        independence_rules={}, selection_stopping_policy={},
        frozen_analysis_fields=("estimator",), code_revision=S1_CODE_REVISION))
    datasets = {}
    for split, reps in ((SplitAssignment.DEV, tuple(S1_DEV_SEEDS)),
                        (SplitAssignment.HELD_OUT, tuple(S1_HELDOUT_SEEDS))):
        datasets[split.value] = store.store(CalibrationDatasetManifest(
            dataset_id=f"ds-s1-{split.value.lower()}", plan_hash=plan_h, scope_hash=scope_h,
            calibration_class=CalibrationClass.ISOTROPIC_BROWNIAN,
            parameter_cell_ids=("cell-a",),
            trajectory_ids=tuple(f"traj-{rep}" for rep in reps),
            truth_record_hashes=(truth_h,), split_assignment=split,
            generator_spec_hashes=(gen_h,), artifact_manifest_hashes=(),
            attempted_replicate_ids=reps))
    return {"scope": scope_h, "truth": truth_h, "generator": gen_h,
            "plan": plan_h, "datasets": datasets}
