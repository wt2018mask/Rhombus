"""CLI for replay-verified X -> N -> S -> OUT production synthesis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rudeus.science.contracts import ClaimAssessment
from rudeus.science.xnsout_production import (
    XNSOUTProductionError,
    build_xnsout_records,
    persist_xnsout_records,
)


def _read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--x-record", action="append", default=[])
    parser.add_argument("--n-record", action="append", default=[])
    parser.add_argument("--s-output", required=True)
    parser.add_argument("--out-output", required=True)
    args = parser.parse_args(argv)

    try:
        primary = ClaimAssessment.from_dict(_read_json(args.primary))
        x_records = tuple(_read_json(p) for p in args.x_record)
        n_records = tuple(_read_json(p) for p in args.n_record)

        bundle = build_xnsout_records(
            primary=primary,
            x_records=x_records,
            n_records=n_records,
        )
        persisted = persist_xnsout_records(
            bundle=bundle,
            s_path=args.s_output,
            out_path=args.out_output,
        )
    except (OSError, json.JSONDecodeError, ValueError, TypeError, XNSOUTProductionError) as exc:
        print(json.dumps({
            "execution_status": "FAILED",
            "reason": str(exc),
        }))
        return 1

    print(json.dumps({
        "execution_status": "COMPLETED",
        "final_disposition": bundle["final_disposition"],
        "final_claim_verdict": bundle["final_claim_verdict"],
        **persisted,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
