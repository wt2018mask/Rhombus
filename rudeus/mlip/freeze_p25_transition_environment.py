"""Freeze the current canonical P2.5 transition execution environment."""

from __future__ import annotations

import argparse
import json

from rudeus.mlip.p25_transition_environment import write_transition_environment


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    payload = write_transition_environment(args.out)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
