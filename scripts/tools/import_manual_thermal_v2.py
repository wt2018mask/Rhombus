"""Revalidate a manual archive with the version 2 offline importer."""
import argparse
import json
from pathlib import Path
from rhombus.atomistics.manual_import_v2 import import_manual_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--request', type=Path, default=Path('data/development/manual0202/owner_request_v1.json'))
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--archive-sha256')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = import_manual_result(args.archive, json.loads(args.request.read_bytes()), args.output_dir,
                                  root=root, expected_archive_sha256=args.archive_sha256)
    print(json.dumps({k: v for k, v in report.items() if k not in ('evidence_records', 'numerical_verification')}))
    print('MCP snapshot:', args.output_dir / 'evidence-v2.jsonl')


if __name__ == '__main__':
    main()
