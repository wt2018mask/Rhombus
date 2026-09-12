"""LiIon empirical dataset loader.

HARD ARCHITECTURAL INVARIANTS (from AGENTS.md §6):
  - This dataset is NEVER merged with OBELiX rows.
  - Temperature dimension is NEVER averaged away; temperature-resolved
    measurements are essential for activation barrier extraction.
  - No re-splitting or re-shuffling of the published data.

Source:
    LiIonDatabase.csv (~820 entries) — temperature-resolved experimental
    ionic conductivity from the supplementary dataset accompanying OBELiX.
    Path: data/obelix/data/misc/LiIonDatabase.csv
    Columns: ID, composition, source, temperature, target, log_target,
             family, ChemicalFamily
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------
LIION_RT_MIN_C: float = 18.0   # Lower bound for "room-temperature" window (°C)
LIION_RT_MAX_C: float = 32.0   # Upper bound for "room-temperature" window (°C)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LiIonIntegrityReport:
    """Summary of data-loading hygiene for the LiIon dataset."""
    total_rows: int
    rows_with_null_family: int
    temperature_min_c: float
    temperature_max_c: float
    n_families_distinct: int
    family_counts: Dict[str, int]
    n_rt_rows: int          # Rows with 18 <= temperature <= 32 C
    n_sulfide_rows: int     # All sulfide rows regardless of temperature
    n_sulfide_rt_rows: int  # RT sulfide rows


# ---------------------------------------------------------------------------
# LiIon loader
# ---------------------------------------------------------------------------
class LiIonDataset:
    """Loader for the temperature-resolved LiIon ionic-conductivity dataset.

    INVARIANT: This class must never be used to merge rows into OBELiX.
    INVARIANT: The ``temperature`` column must be preserved as a float column
               and must never be collapsed by averaging or groupby-aggregation
               within this class.

    Usage example::

        ds = LiIonDataset("data/obelix/data/misc/LiIonDatabase.csv")
        rt_sulfides = ds.filter(temperature_range=(18.0, 32.0), family="sulfide")
    """

    def __init__(self, csv_path: Union[str, Path]) -> None:
        self.csv_path = Path(csv_path)
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"LiIon CSV not found at {self.csv_path!r}. "
                "Check config.yaml liion_source path."
            )
        self._load()

    def _load(self) -> None:
        """Load raw CSV and build the integrity report.

        IMPORTANT: Does NOT impute or drop rows with null ChemicalFamily —
        those are retained in self.df to avoid silent data loss.  Callers
        can filter on is_family_known if needed.
        """
        raw = pd.read_csv(self.csv_path)

        # Normalise column names (strip whitespace)
        raw.columns = [c.strip() for c in raw.columns]

        required_cols = {"ID", "composition", "temperature", "target"}
        missing = required_cols - set(raw.columns)
        if missing:
            raise KeyError(
                f"LiIon CSV is missing required columns: {sorted(missing)}. "
                f"Found: {sorted(raw.columns)}"
            )

        # Drop rows with non-finite conductivity (target) or temperature
        # — never silently impute, flag counts explicitly.
        before = len(raw)
        finite_mask = (
            np.isfinite(raw["temperature"].values)
            & np.isfinite(raw["target"].values)
            & (raw["target"].values > 0)
        )
        raw = raw[finite_mask].copy()
        self._dropped_non_finite = before - len(raw)

        # Mark rows with null ChemicalFamily so callers can filter if needed
        raw["is_family_known"] = raw["ChemicalFamily"].notna()

        # Normalised family string (lower-case, strip whitespace)
        raw["family_lower"] = raw["ChemicalFamily"].fillna("").str.strip().str.lower()

        # log_target fallback if column missing or non-finite
        if "log_target" not in raw.columns:
            raw["log_target"] = np.log10(raw["target"])
        else:
            bad_log = ~np.isfinite(raw["log_target"])
            raw.loc[bad_log, "log_target"] = np.log10(raw.loc[bad_log, "target"])

        self.df: pd.DataFrame = raw

        # Build integrity report
        temp_vals = self.df["temperature"].values
        rt_mask = (temp_vals >= LIION_RT_MIN_C) & (temp_vals <= LIION_RT_MAX_C)

        all_families = raw["family_lower"].value_counts().to_dict()
        n_sulfide = int(raw["family_lower"].str.contains("sulph|sulfid", regex=True, na=False).sum())
        rt_sulfide = int(
            (rt_mask & raw["family_lower"].str.contains("sulph|sulfid", regex=True, na=False)).sum()
        )

        self.integrity_report = LiIonIntegrityReport(
            total_rows=len(self.df),
            rows_with_null_family=int((~self.df["is_family_known"]).sum()),
            temperature_min_c=float(np.min(temp_vals)),
            temperature_max_c=float(np.max(temp_vals)),
            n_families_distinct=int(self.df["is_family_known"].sum() > 0 and len(all_families)),
            family_counts=all_families,
            n_rt_rows=int(rt_mask.sum()),
            n_sulfide_rows=n_sulfide,
            n_sulfide_rt_rows=rt_sulfide,
        )

    # ------------------------------------------------------------------
    # Slicing interface
    # ------------------------------------------------------------------

    def filter(
        self,
        temperature_range: Optional[tuple] = None,
        family: Optional[str] = None,
        known_family_only: bool = False,
    ) -> pd.DataFrame:
        """Return a filtered slice of the LiIon dataset.

        NEVER averages across temperatures — the full temperature-resolved
        table is always returned.

        Args:
            temperature_range: (T_min_C, T_max_C) inclusive.  None = no filter.
            family:            Substring match on ChemicalFamily (case-insensitive).
                               E.g. "sulfid" matches "Sulphides", "Sulphides and Other...".
            known_family_only: If True, exclude rows with null ChemicalFamily.

        Returns:
            Filtered pd.DataFrame view (no copy, read-only).
        """
        mask = pd.Series(np.ones(len(self.df), dtype=bool), index=self.df.index)

        if temperature_range is not None:
            t_min, t_max = temperature_range
            temp = self.df["temperature"]
            mask &= (temp >= t_min) & (temp <= t_max)

        if family is not None:
            family_lower = family.strip().lower()
            mask &= self.df["family_lower"].str.contains(family_lower, na=False, regex=False)

        if known_family_only:
            mask &= self.df["is_family_known"]

        return self.df[mask]

    def rt_slice(self, family: Optional[str] = None) -> pd.DataFrame:
        """Convenience: room-temperature slice (18–32 °C)."""
        return self.filter(
            temperature_range=(LIION_RT_MIN_C, LIION_RT_MAX_C),
            family=family,
        )

    def sulfide_rt_slice(self) -> pd.DataFrame:
        """Convenience: RT sulfide rows (matches 'sulph' in ChemicalFamily)."""
        return self.rt_slice(family="sulph")
