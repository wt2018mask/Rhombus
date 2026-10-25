"""Run the frozen local 0198 retrospective label-reveal study; no network."""
import argparse
import json
from pathlib import Path

from rhombus.qualification.observation_budget import run_study


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        p.error("output already exists; preserve earlier observations")
    report = run_study()
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps({"hypotheses": report["hypotheses"], "cost": report["cost"]}))


if __name__ == "__main__":
    main()
