#!/usr/bin/env python3
import json

from rudeus.science.known_material_b5_p0_semantics import (
    classify_exact_member_neutrality,
)
from scripts.benchmark.render_b5_dev_structure_units import (
    build_canonical_b5_dev_structure_units,
)
from scripts.benchmark.run_b5_dev_p0 import build_canonical_b5_p0_report


def main() -> int:
    units = build_canonical_b5_dev_structure_units()
    report = build_canonical_b5_p0_report()
    llzo_units = [
        unit for unit in units.units
        if unit.material_key == "llzo-cubic-al-stabilized"
    ]
    labels = {unit.component_label for unit in llzo_units}
    observations = [
        item for item in report.observations
        if item.material_key == "llzo-cubic-al-stabilized"
        and item.component_label in labels
    ]
    observations.sort(key=lambda item: item.component_label)
    result = classify_exact_member_neutrality(
        material_key="llzo-cubic-al-stabilized",
        representation_mode="ENSEMBLE",
        member_neutrality=tuple(item.neutrality_ok for item in observations),
        member_geometry=tuple(item.geometry_ok for item in observations),
        member_pauling=tuple(item.pauling_ok for item in observations),
        weighted_ensemble=all(
            unit.weight_numerator is not None and unit.weight_denominator is not None
            for unit in llzo_units
        ),
        source_marginals_only=True,
    )
    print(json.dumps(result.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
