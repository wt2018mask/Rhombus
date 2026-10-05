"""Scientific design freeze for the blind known-material falsification benchmark.

B0 defines the benchmark rules before any material identity or literature label is
selected. It does not tune scientific thresholds or authorize production search.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from rudeus.science.contracts import Record, UNRESOLVED


PROTOCOL_VERSION = "known-material-falsification-benchmark-v1"
STAGES = ("P0", "P1", "P2", "P2.5", "P3", "X", "N", "S", "APPLICATION")


class TruthClass(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BORDERLINE = "BORDERLINE"
    FAILURE_CONTROL = "FAILURE_CONTROL"


class TruthEvidenceClass(str, Enum):
    DIRECT_EXPERIMENTAL = "DIRECT_EXPERIMENTAL"
    MULTIPLE_EXPERIMENTAL = "MULTIPLE_EXPERIMENTAL"
    REFERENCE_COMPUTATION = "REFERENCE_COMPUTATION"
    CONSENSUS_REFERENCE = "CONSENSUS_REFERENCE"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"


class BenchmarkDecision(str, Enum):
    QUALIFIED = "QUALIFIED"
    RECALIBRATION_REQUIRED = "RECALIBRATION_REQUIRED"
    PIPELINE_BLOCKED = "PIPELINE_BLOCKED"


@dataclass(frozen=True, kw_only=True)
class BlindingPolicy(Record):
    visible_fields: tuple[str, ...]
    sealed_fields: tuple[str, ...]
    unblind_after_frozen_results_only: bool = True

    def validate(self):
        super().validate()
        required_visible = {"benchmark_id", "split", "structure_hash", "benchmark_protocol_hash"}
        required_sealed = {"material_identity", "truth_class", "literature_evidence",
                           "expected_stage_outcomes"}
        if not required_visible.issubset(self.visible_fields):
            raise ValueError("benchmark execution identity incomplete")
        if not required_sealed.issubset(self.sealed_fields):
            raise ValueError("scientific labels must remain sealed")
        if set(self.visible_fields) & set(self.sealed_fields):
            raise ValueError("sealed labels cannot be execution-visible")
        if self.unblind_after_frozen_results_only is not True:
            raise ValueError("unblinding requires frozen blinded results")


@dataclass(frozen=True, kw_only=True)
class SplitPolicy(Record):
    dev_tuning_allowed: bool = True
    held_out_tuning_allowed: bool = False
    held_out_membership_immutable: bool = True
    unblinded_held_out_reusable: bool = False
    bootstrap_resamples_independent_datasets: bool = False

    def validate(self):
        super().validate()
        if self.dev_tuning_allowed is not True:
            raise ValueError("DEV must remain available for calibration")
        if self.held_out_tuning_allowed is not False:
            raise ValueError("HELD_OUT cannot tune scientific criteria")
        if self.held_out_membership_immutable is not True:
            raise ValueError("HELD_OUT membership must be immutable")
        if self.unblinded_held_out_reusable is not False:
            raise ValueError("unblinded HELD_OUT cannot be reused as held out")
        if self.bootstrap_resamples_independent_datasets is not False:
            raise ValueError("bootstrap resamples are not independent scientific datasets")


@dataclass(frozen=True, kw_only=True)
class IngressPolicy(Record):
    bypass_generation: bool = True
    first_stage: str = "P0"
    generation_claims_authorized: bool = False
    production_candidate_promotion_authorized: bool = False

    def validate(self):
        super().validate()
        if self.bypass_generation is not True or self.first_stage != "P0":
            raise ValueError("known-material controls must bypass G and enter at P0")
        if self.generation_claims_authorized is not False:
            raise ValueError("benchmark does not validate G")
        if self.production_candidate_promotion_authorized is not False:
            raise ValueError("benchmark controls are not discovered candidates")


@dataclass(frozen=True, kw_only=True)
class StageRule(Record):
    stage: str
    truth_dimensions: tuple[str, ...]
    falsification_events: tuple[str, ...]
    unsupported_policy: str = "UNKNOWN_OR_INDETERMINATE_NO_EXTRAPOLATION"

    def validate(self):
        super().validate()
        if self.stage not in STAGES:
            raise ValueError("unknown benchmark stage")
        if not self.truth_dimensions or not self.falsification_events:
            raise ValueError("stage falsification rule incomplete")
        if self.unsupported_policy != "UNKNOWN_OR_INDETERMINATE_NO_EXTRAPOLATION":
            raise ValueError("unsupported regimes cannot be silently extrapolated")


@dataclass(frozen=True, kw_only=True)
class EvaluationPolicy(Record):
    metrics: tuple[str, ...]
    scalar_score_forbidden: bool = True
    numeric_threshold_status: str = UNRESOLVED
    numeric_thresholds: Mapping[str, float] = None

    def __post_init__(self):
        if self.numeric_thresholds is None:
            object.__setattr__(self, "numeric_thresholds", {})
        super().__post_init__()

    def validate(self):
        super().validate()
        required = {
            "sensitivity", "specificity", "false_negative_rate", "false_positive_rate",
            "unknown_rate", "indeterminate_rate", "cumulative_positive_retention",
            "stage_attributed_false_rejection", "chemistry_family_stratification",
            "temperature_regime_stratification", "model_disagreement_rate",
        }
        if not required.issubset(self.metrics):
            raise ValueError("benchmark metrics incomplete")
        if self.scalar_score_forbidden is not True:
            raise ValueError("benchmark cannot collapse into a scalar score")
        if self.numeric_threshold_status != UNRESOLVED or self.numeric_thresholds:
            raise ValueError("B0 must not invent numeric qualification thresholds")


@dataclass(frozen=True, kw_only=True)
class KnownMaterialBenchmarkProtocol(Record):
    benchmark_protocol_version: str
    stages: tuple[str, ...]
    truth_classes: tuple[str, ...]
    truth_evidence_classes: tuple[str, ...]
    blinding: BlindingPolicy
    split: SplitPolicy
    ingress: IngressPolicy
    evaluation: EvaluationPolicy
    stage_rules: tuple[StageRule, ...]
    decisions: tuple[str, ...]
    threshold_mutation_authorized: bool = False
    historical_reinterpretation_authorized: bool = False
    production_search_authorized: bool = False

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        value["blinding"] = BlindingPolicy.from_dict(value["blinding"])
        value["split"] = SplitPolicy.from_dict(value["split"])
        value["ingress"] = IngressPolicy.from_dict(value["ingress"])
        value["evaluation"] = EvaluationPolicy.from_dict(value["evaluation"])
        value["stage_rules"] = tuple(StageRule.from_dict(v) for v in value["stage_rules"])
        return cls(**value)

    def validate(self):
        super().validate()
        if self.benchmark_protocol_version != PROTOCOL_VERSION or tuple(self.stages) != STAGES:
            raise ValueError("benchmark protocol identity or stage order differs")
        if tuple(self.truth_classes) != tuple(v.value for v in TruthClass):
            raise ValueError("truth-class vocabulary differs")
        if tuple(self.truth_evidence_classes) != tuple(v.value for v in TruthEvidenceClass):
            raise ValueError("truth-evidence vocabulary differs")
        if tuple(r.stage for r in self.stage_rules) != STAGES:
            raise ValueError("each stage requires one ordered falsification rule")
        if tuple(self.decisions) != tuple(v.value for v in BenchmarkDecision):
            raise ValueError("benchmark decision vocabulary differs")
        if any((self.threshold_mutation_authorized,
                self.historical_reinterpretation_authorized,
                self.production_search_authorized)):
            raise ValueError("B0 grants no science mutation, reinterpretation, or production authorization")


_STAGE_RULES = {
    "P0": (("chemical_plausibility", "geometry_plausibility", "representation_support"),
           ("known_real_material_false_rejection", "failure_control_false_acceptance")),
    "P1": (("phase_identity", "relaxation_stability", "model_domain_support"),
           ("stable_phase_false_rejection", "model_domain_error_as_material_failure")),
    "P2": (("framework_dynamic_stability", "mobile_sublattice_motion", "temperature_regime"),
           ("stable_framework_false_rejection", "failure_control_false_acceptance",
            "mobile_disorder_as_framework_collapse")),
    "P2.5": (("self_diffusion_state", "trajectory_support", "mobile_ion_population",
              "temperature_regime"),
             ("fast_ion_false_nondiffusive", "poor_conductor_false_diffusive",
              "insufficient_sampling_forced_resolved")),
    "P3": (("self_diffusion_magnitude", "temperature_dependence", "activation_regime",
            "uncertainty_support"),
           ("reference_transport_inconsistency", "unsupported_regime_extrapolation",
            "experimental_conductivity_as_self_diffusion_truth")),
    "X": (("primary_model_support", "secondary_model_support", "training_independence", "agreement"),
          ("unqualified_model_agreement_as_pass", "systematic_primary_model_error_hidden")),
    "N": (("known_material_rediscovery", "reference_coverage", "structure_identity"),
          ("known_material_classified_novel", "incomplete_reference_universe_as_novel_pass")),
    "S": (("experimental_synthesis_status", "phase_identity", "route_evidence"),
          ("synthesized_material_false_unsynthesizable", "computed_only_as_synthesized")),
    "APPLICATION": (("profile_identity", "operating_conditions", "compatibility_evidence"),
                    ("unsupported_application_claim_pass", "profile_mismatch_extrapolated")),
}


def build_known_material_benchmark_protocol() -> KnownMaterialBenchmarkProtocol:
    """Build B0 without selecting any material, label, or numeric acceptance threshold."""
    return KnownMaterialBenchmarkProtocol(
        benchmark_protocol_version=PROTOCOL_VERSION,
        stages=STAGES,
        truth_classes=tuple(v.value for v in TruthClass),
        truth_evidence_classes=tuple(v.value for v in TruthEvidenceClass),
        blinding=BlindingPolicy(
            visible_fields=("benchmark_id", "split", "structure_hash", "benchmark_protocol_hash"),
            sealed_fields=("material_identity", "truth_class", "literature_evidence",
                           "expected_stage_outcomes"),
        ),
        split=SplitPolicy(),
        ingress=IngressPolicy(),
        evaluation=EvaluationPolicy(metrics=(
            "sensitivity", "specificity", "false_negative_rate", "false_positive_rate",
            "unknown_rate", "indeterminate_rate", "cumulative_positive_retention",
            "stage_attributed_false_rejection", "chemistry_family_stratification",
            "temperature_regime_stratification", "model_disagreement_rate",
        )),
        stage_rules=tuple(StageRule(stage=s, truth_dimensions=_STAGE_RULES[s][0],
                                    falsification_events=_STAGE_RULES[s][1]) for s in STAGES),
        decisions=tuple(v.value for v in BenchmarkDecision),
    )
