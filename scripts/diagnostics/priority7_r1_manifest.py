"""Content-addressed manifest for final Stage R1 outputs."""
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 base=ROOT/'data/benchmarks/v3_static';files=[base/'priority7_r1_analytical_v5.json',base/'priority7_r1_summary_v1.json']
 for m in ('li2s','lialo2','llzo'):
  for n in (16,20,24):
   for o in ('0','0.5'):
    prefix=f'priority7_{m}_n{n}_o{o}';files.extend([base/(prefix+'_joint_r1_v4.json'),base/(prefix+'_clearance_r1_v3.json')])
 code=['rhombus/transport/periodic_clearance.py','rhombus/transport/soft_clearance.py','rhombus/transport/segment_percolation.py','scripts/diagnostics/priority7_joint.py','scripts/diagnostics/priority7_clearance.py','scripts/diagnostics/priority7_summary.py','scripts/diagnostics/priority7_analytical_m0.py','scripts/diagnostics/priority7_r1_manifest.py']
 out={'schema':'priority7-stage-r1-manifest-v1','base_commit':'93e2c420362e55a5de1ef13267d05e37ab07755f','outputs_sha256':{str(x.relative_to(ROOT)):h(x) for x in files},'code_sha256':{x:h(ROOT/x) for x in code},'qualification':'ABSTAIN'};a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
