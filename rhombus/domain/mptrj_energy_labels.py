"""Explicit MPTrj frame energy label semantics, not a MACE training attestation.

The public CHGNet MPTrj JSON defines its energy_per_atom as MP2020-corrected
per-atom energy. This MUST NOT silently be treated as a raw VASP DFT training
target for a MACE checkpoint. Official MACE-MP docs discuss raw VASP energies,
but the exact MACE-MPA-0 preprocessing/selection is still UNATTESTED.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


class MPTrjEnergyLabelError(ValueError):
    """A reported energy label has an invalid value or context."""


@dataclass(frozen=True)
class MPTrjFrameEnergyProvenance:
    """Observations about source labels only; no model training eligibility.

    None indicates an absent source field, not a value of zero.
    """
    raw_vasp_total_energy_ev: float | None
    mp2020_corrected_total_energy_ev: float | None
    chgnet_mp2020_corrected_energy_per_atom_ev: float | None
    raw_and_corrected_total_energy_differ: bool | None
    source_label_identity: str = "CHGNET_MPTRJ_ORIGINAL_JSON"
    model_training_label_identity: str = "MACE_MPA0_EXACT_LABEL_SELECTION_UNATTESTED"
    raw_label_can_be_assumed_mace_mpa0_training_target: bool = False
    corrected_label_can_be_assumed_mace_mpa0_training_target: bool = False
    allows_energy_calibration_from_this_frame: bool = False


def _optional_finite_number(frame: Mapping[str, object], key: str) -> float | None:
    if key not in frame or frame[key] is None:
        return None
    value = frame[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MPTrjEnergyLabelError(f"MPTrj {key} must be a finite numeric energy")
    number = float(value)
    if not math.isfinite(number):
        raise MPTrjEnergyLabelError(f"MPTrj {key} must be a finite numeric energy")
    return number


def inspect_mptrj_frame_energy_labels(
    frame: Mapping[str, object],
) -> MPTrjFrameEnergyProvenance:
    """Preserve observed corrected and raw energy fields without conflation.

    Does not invent an energy value, undo MP2020 correction, infer the MACE
    checkpoint's training selection, or override any scientific claim gate.
    """
    raw = _optional_finite_number(frame, "uncorrected_total_energy")
    corrected = _optional_finite_number(frame, "corrected_total_energy")
    per_atom = _optional_finite_number(frame, "energy_per_atom")
    changed = (raw != corrected) if raw is not None and corrected is not None else None
    return MPTrjFrameEnergyProvenance(
        raw_vasp_total_energy_ev=raw,
        mp2020_corrected_total_energy_ev=corrected,
        chgnet_mp2020_corrected_energy_per_atom_ev=per_atom,
        raw_and_corrected_total_energy_differ=changed,
    )


def require_mace_mpa0_energy_training_label_provenance(
    provenance: MPTrjFrameEnergyProvenance,
) -> None:
    """Conservative policy: a source frame cannot attest MACE training labels.

    Intentional hard block. A future version requires independently verified
    checkpoint-bound preprocessing and frame-selection evidence before adding
    an authorization path. Presence of raw energies alone proves nothing about
    the checkpoint's actual selected inputs.
    """
    raise MPTrjEnergyLabelError(
        "MACE-MPA-0 exact training energy representation is UNATTESTED; "
        "MPTrj raw/corrected source labels cannot authorize calibration"
    )
