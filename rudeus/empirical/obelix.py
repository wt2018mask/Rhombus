"""OBELiX empirical benchmark dataset loader and integrity audit.

HARD ARCHITECTURAL INVARIANT:
The empirical anchor is the OBELiX dataset (github.com/NRC-Mila/OBELiX) using its
OFFICIALLY PUBLISHED leakage-aware grouped train/test split.
This split must NEVER be re-shuffled, re-partitioned, or re-generated locally.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import pandas as pd

from pymatgen.core import Composition, Structure


@dataclass(frozen=True)
class DatasetIntegrityReport:
    """Report detailing data hygiene and leakage audits upon loading OBELiX."""
    total_row_count: int
    train_row_count: int
    test_row_count: int
    cif_linked_count: int
    dropped_non_finite_count: int
    leaked_formula_keys_count: int
    leaked_formula_samples: List[str]
    superionic_test_count: int
    superionic_test_fraction: float


def normalize_formula(comp_str: str) -> str:
    """Derive reduced composition formula for leakage audit."""
    try:
        return Composition(comp_str).reduced_formula
    except Exception:
        return str(comp_str).strip()


def classify_chemical_family(composition_str: str) -> str:
    """Classify chemical family (oxide, sulfide, halide, etc.) from chemical composition."""
    try:
        comp = Composition(composition_str)
        elements = set(el.symbol for el in comp.elements)
    except Exception:
        return "unknown"

    has_o = "O" in elements
    has_s = any(e in elements for e in ["S", "Se", "Te"])
    has_x = any(e in elements for e in ["F", "Cl", "Br", "I"])

    if has_s and not has_o and not has_x:
        return "sulfide"
    elif has_o and not has_s and not has_x:
        return "oxide"
    elif has_x and not has_o and not has_s:
        return "halide"
    elif has_s and has_o and not has_x:
        return "oxysulfide"
    elif has_o and has_x and not has_s:
        return "oxyhalide"
    elif has_s and has_x and not has_o:
        return "thiohalide"
    elif has_s:
        return "sulfide"
    elif has_o:
        return "oxide"
    elif has_x:
        return "halide"
    return "other"


class OBELiXDataset:
    """Loader and manager for the official NRC-Mila OBELiX dataset."""

    def __init__(self, repo_path: Union[str, Path]):
        self.repo_path = Path(repo_path)
        self.data_dir = self.repo_path / "data"
        self.cif_dir = self.data_dir / "randomized_cifs"

        self.processed_csv_path = self.data_dir / "processed.csv"
        self.train_idx_path = self.data_dir / "train_idx.csv"
        self.test_idx_path = self.data_dir / "test_idx.csv"

        if not self.processed_csv_path.exists():
            raise FileNotFoundError(
                f"OBELiX processed.csv not found at {self.processed_csv_path}. "
                "Ensure OBELiX repository is cloned."
            )
        if not self.train_idx_path.exists() or not self.test_idx_path.exists():
            raise FileNotFoundError(
                "Official OBELiX split indices (train_idx.csv / test_idx.csv) missing!"
            )

        self._load_and_audit()

    def _load_and_audit(self) -> None:
        """Load dataset using published split and execute integrity audits."""
        raw_df = pd.read_csv(self.processed_csv_path)

        train_ids: Set[str] = set(pd.read_csv(self.train_idx_path)["ID"].astype(str))
        test_ids: Set[str] = set(pd.read_csv(self.test_idx_path)["ID"].astype(str))

        raw_df["ID"] = raw_df["ID"].astype(str)

        # Check for dropped/non-finite conductivities (NEVER silently imputed)
        cond_col = "Ionic conductivity (S cm-1)"
        if cond_col not in raw_df.columns:
            raise KeyError(f"Expected column '{cond_col}' not found in processed.csv")

        valid_cond_mask = np.isfinite(raw_df[cond_col]) & (raw_df[cond_col] > 0)
        dropped_non_finite = int((~valid_cond_mask).sum())
        # Filter strictly if any non-finite existed (never impute)
        self.df = raw_df[valid_cond_mask].copy()

        # Check CIF linking
        cif_files = set(os.listdir(self.cif_dir)) if self.cif_dir.exists() else set()
        self.df["has_cif"] = self.df["ID"].apply(lambda x: f"{x}.cif" in cif_files)
        cif_linked_count = int(self.df["has_cif"].sum())

        # Classify chemical family
        self.df["chemical_family"] = self.df["Composition"].apply(classify_chemical_family)

        # Partition by official split
        self.train_df = self.df[self.df["ID"].isin(train_ids)].copy()
        self.test_df = self.df[self.df["ID"].isin(test_ids)].copy()

        # Audit for composition key leakage between official train and test
        train_formulas = set(self.train_df["Composition"].apply(normalize_formula))
        test_formulas = set(self.test_df["Composition"].apply(normalize_formula))
        leaked_keys = train_formulas.intersection(test_formulas)

        # Superionic stats on test (cutoff >= 1e-3 S/cm PROVISIONAL)
        superionic_mask = self.test_df[cond_col] >= 1e-3
        superionic_count = int(superionic_mask.sum())
        superionic_frac = float(superionic_count / len(self.test_df)) if len(self.test_df) > 0 else 0.0

        self.integrity_report = DatasetIntegrityReport(
            total_row_count=len(self.df),
            train_row_count=len(self.train_df),
            test_row_count=len(self.test_df),
            cif_linked_count=cif_linked_count,
            dropped_non_finite_count=dropped_non_finite,
            leaked_formula_keys_count=len(leaked_keys),
            leaked_formula_samples=sorted(list(leaked_keys))[:5],
            superionic_test_count=superionic_count,
            superionic_test_fraction=superionic_frac,
        )

    def get_structure(self, entry_id: str) -> Optional[Structure]:
        """Load crystal Structure for an entry from randomized_cifs if available."""
        cif_path = self.cif_dir / f"{entry_id}.cif"
        if not cif_path.exists():
            return None
        try:
            return Structure.from_file(str(cif_path))
        except Exception:
            return None
