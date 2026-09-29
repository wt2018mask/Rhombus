"""Deterministic, observational parent view of a persisted diagnostic panel."""

from __future__ import annotations

from collections import defaultdict


_METRICS = ("novel", "useful", "geometry_fail", "p0_plausible")
_FRACTION_EDGES = [0.0, 0.25, 0.5, 1.0]


def _metrics(rows):
    generated = [row for row in rows if row["diagnostic_state"] == "GENERATED"]
    counts = {
        "novel": sum(row["novelty_tag"] == "novel" for row in generated),
        "useful": sum(
            row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE"
            for row in generated
        ),
        "geometry_fail": sum(row["p0_geometry_ok"] is False for row in generated),
        "p0_plausible": sum(row["p0_state"] == "PLAUSIBLE" for row in generated),
    }
    denominator = len(generated)
    return {
        **{f"{name}_count": counts[name] for name in _METRICS},
        **{
            f"{name}_frequency": counts[name] / denominator if denominator else 0.0
            for name in _METRICS
        },
    }


def _parent_summary(parents):
    count = len(parents)
    ever_useful = sum(parent["useful_count"] > 0 for parent in parents)
    return {
        "parent_count": count,
        "generated_parent_count": sum(parent["generated_observations"] > 0 for parent in parents),
        "never_useful_parent_count": count - ever_useful,
        "ever_useful_parent_count": ever_useful,
        "persistent_useful_parent_count": sum(
            parent["behavioral_flags"]["PERSISTENT_USEFUL"] for parent in parents
        ),
        "geometry_fragile_parent_count": sum(
            parent["behavioral_flags"]["GEOMETRY_FRAGILE"] for parent in parents
        ),
        "always_geometry_fail_parent_count": sum(
            parent["behavioral_flags"]["ALWAYS_GEOMETRY_FAIL"] for parent in parents
        ),
    }


def _concentration(parents, metric):
    ranked = sorted(
        ({"parent_id": parent["parent_id"], "count": parent[f"{metric}_count"]}
         for parent in parents),
        key=lambda item: (-item["count"], item["parent_id"]),
    )
    total = sum(item["count"] for item in ranked)

    def parents_to_reach(fraction):
        if not total:
            return 0
        running = 0
        for index, item in enumerate(ranked, 1):
            running += item["count"]
            if running >= fraction * total:
                return index
        return len(ranked)

    return {
        "observations_count": total,
        "parents_for_50_percent": parents_to_reach(0.5),
        "parents_for_80_percent": parents_to_reach(0.8),
        "max_single_parent_share": ranked[0]["count"] / total if total else 0.0,
        "parent_counts_descending": ranked,
    }


def _fraction_bin(value):
    if value == 0:
        return "0"
    for lower, upper in zip(_FRACTION_EDGES, _FRACTION_EDGES[1:]):
        if lower < value <= upper:
            return f"({lower:g},{upper:g}]"
    raise ValueError("target fraction must be in [0, 1]")


def build_mobile_ion_parent_diagnostic_atlas(panel_payload, *, source_artifact_sha256=None):
    """Derive a JSON-ready atlas exclusively from panel metadata and raw rows."""
    metadata = panel_payload["metadata"]
    sigmas = metadata["sigma_values_A_provisional"]
    seeds = metadata["base_seeds"]
    threshold = metadata["persistent_useful_threshold"]
    rows_by_parent = defaultdict(list)
    for row in panel_payload["rows"]:
        rows_by_parent[row["parent_id"]].append(row)

    parents = []
    for parent_id in metadata["ordered_parent_ids"]:
        rows = rows_by_parent[parent_id]
        if not rows:
            raise ValueError(f"missing raw observations for {parent_id}")
        first = rows[0]
        site_count = first["site_count"]
        if site_count <= 0:
            raise ValueError(f"invalid site_count for {parent_id}")
        generated_count = sum(row["diagnostic_state"] == "GENERATED" for row in rows)
        per_sigma = []
        for sigma in sigmas:
            sigma_rows = [row for row in rows if row["sigma_A_provisional"] == sigma]
            by_seed = {row["base_seed"]: row for row in sigma_rows}
            if len(by_seed) != len(sigma_rows) or set(by_seed) != set(seeds):
                raise ValueError(f"incomplete or duplicate observations for {parent_id} at {sigma}")
            outcomes = [
                (row["novelty_tag"] == "novel" and row["p0_state"] == "PLAUSIBLE")
                if (row := by_seed[seed])["diagnostic_state"] == "GENERATED" else None
                for seed in seeds
            ]
            sigma_generated = sum(row["diagnostic_state"] == "GENERATED" for row in sigma_rows)
            useful_seed_count = sum(outcome is True for outcome in outcomes)
            per_sigma.append({
                "sigma_A_provisional": sigma,
                "ordered_seeds": list(seeds),
                "useful_by_seed": outcomes,
                "useful_seed_count": useful_seed_count,
                "useful_seed_fraction": useful_seed_count / sigma_generated if sigma_generated else 0.0,
                "generated_count": sigma_generated,
                **_metrics(sigma_rows),
            })

        metrics = _metrics(rows)
        useful_count = metrics["useful_count"]
        geometry_fail_count = metrics["geometry_fail_count"]
        persistent = any(
            item["generated_count"] > 0 and item["useful_frequency"] >= threshold
            for item in per_sigma
        )

        def first_sigma(metric):
            matching = [
                item["sigma_A_provisional"] for item in per_sigma
                if item[f"{metric}_count"] > 0
            ]
            return min(matching) if matching else None

        parents.append({
            "parent_id": parent_id,
            "chemical_family": first["parent_chemical_family"],
            "site_count": site_count,
            "target_site_count": first["target_site_count"],
            "target_fraction": first["target_site_count"] / site_count,
            "generated_observations": generated_count,
            "blocked_observations": sum(row["diagnostic_state"] == "BLOCKED_BY_PARENT_P0" for row in rows),
            "inapplicable_observations": sum(row["diagnostic_state"] == "INAPPLICABLE" for row in rows),
            **metrics,
            "per_sigma": per_sigma,
            "useful_frequency_by_sigma": [item["useful_frequency"] for item in per_sigma],
            "geometry_fail_frequency_by_sigma": [item["geometry_fail_frequency"] for item in per_sigma],
            "useful_seed_variability": any(
                True in item["useful_by_seed"] and False in item["useful_by_seed"]
                for item in per_sigma
            ),
            "first_novel_sigma": first_sigma("novel"),
            "first_useful_sigma": first_sigma("useful"),
            "first_geometry_fail_sigma": first_sigma("geometry_fail"),
            "behavioral_flags": {
                "NO_GENERATED_EVIDENCE": generated_count == 0,
                "NEVER_NOVEL": generated_count > 0 and metrics["novel_count"] == 0,
                "PERSISTENT_USEFUL": persistent,
                "INTERMITTENT_USEFUL": useful_count > 0 and not persistent,
                "ALWAYS_GEOMETRY_FAIL": generated_count > 0 and geometry_fail_count == generated_count,
                "GEOMETRY_FRAGILE": 0 < geometry_fail_count < generated_count,
            },
        })

    def grouped(key):
        groups = defaultdict(list)
        for parent in parents:
            groups[str(key(parent))].append(parent)
        return {name: _parent_summary(groups[name]) for name in sorted(groups)}

    source = {"schema_version": panel_payload["schema_version"], **metadata}
    if source_artifact_sha256 is not None:
        source = {"diagnostic_artifact_sha256": source_artifact_sha256, **source}

    return {
        "schema_version": "mobile-ion-parent-diagnostic-atlas-v1",
        "artifact_type": "OBSERVATIONAL_DIAGNOSTIC",
        "authorization": {
            "scheduler_activation": False,
            "p1_eligibility": False,
            "downstream_scientific_superiority_claim": False,
        },
        "activation_authorized": False,
        "p1_eligibility_authorized": False,
        "downstream_scientific_claims_authorized": False,
        "source": source,
        "parents": parents,
        "summaries": {
            "by_chemical_family": grouped(lambda parent: parent["chemical_family"]),
            "by_site_count": grouped(lambda parent: parent["site_count"]),
            "by_target_site_count": grouped(lambda parent: parent["target_site_count"]),
            "target_fraction_bin_edges": list(_FRACTION_EDGES),
            "by_target_fraction_bin": grouped(lambda parent: _fraction_bin(parent["target_fraction"])),
            "concentration": {
                "useful": _concentration(parents, "useful"),
                "geometry_fail": _concentration(parents, "geometry_fail"),
            },
        },
    }
