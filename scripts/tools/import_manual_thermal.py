"""Compatibility entry point for the corrected version 2 offline importer."""
import argparse
import json
from pathlib import Path
from rhombus.atomistics.manual_import_v2 import import_manual_result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True);p.add_argument('--request',type=Path,
        default=Path('data/development/manual0202/owner_request_v1.json'))
    p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--archive-sha256')
    a=p.parse_args();root=Path(__file__).resolve().parents[2]
    report=import_manual_result(a.archive,json.loads(a.request.read_bytes()),a.output_dir,root=root,
        expected_archive_sha256=a.archive_sha256)
    print(json.dumps({k:v for k,v in report.items() if k not in ('evidence_records','numerical_verification')}))
    print('MCP snapshot:',a.output_dir/'evidence-v2.jsonl')


if __name__=='__main__':main()
