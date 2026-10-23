"""Execute the separately frozen source-out stability diagnostic on local CPU."""
import argparse
import json
from pathlib import Path

from rhombus.qualification.process_choice_stability import run_experiment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence-jsonl', type=Path)
    args = parser.parse_args()
    outputs = [p for p in (args.output, args.evidence_jsonl) if p is not None]
    if len(set(p.resolve() for p in outputs)) != len(outputs) or any(p.exists() for p in outputs):
        parser.error('use distinct new output paths; prior evidence is immutable')
    result = run_experiment(authorized=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    if args.evidence_jsonl:
        args.evidence_jsonl.write_text(''.join(json.dumps(e, sort_keys=True) + '\n' for e in result['evidence_records']))
    print(json.dumps({'findings': result['findings'], 'policy_summaries': result['policy_summaries'], 'cost': result['cost']}))


if __name__ == '__main__':
    main()
