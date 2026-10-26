"""Owner-operated Kaggle CPU launch. No submission API, host flags or retries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from rhombus.atomistics.manual_thermal import consume_owner_launch, validate_manual_request
from rhombus.atomistics.thermal_trace import canonical_bytes
from scripts.science.thermal_study_0201 import ROOT, execute_thermal_workload


def launch(request, model, output, *, confirmation, free_cpu_confirmed=False):
    if not Path('/kaggle/working').is_dir() or not Path('/kaggle/input').is_dir():
        raise PermissionError('owner launch must occur in Kaggle; no local compute fallback')
    if Path('/dev/nvidia0').exists() or os.environ.get('TPU_NAME'):
        raise PermissionError('select CPU / accelerator None; GPU and TPU not approved')
    validate_manual_request(request, ROOT)
    if Path(output).exists():
        raise FileExistsError('preserve earlier output; no retry')
    receipt = consume_owner_launch(Path('/kaggle/working'), request,
        confirmation=confirmation, free_cpu_confirmed=free_cpu_confirmed)
    # This is a separate manual entry point. Never fabricate host_context or
    # call execute_on_kaggle's protected automated-dispatch interface.
    result = execute_thermal_workload(request, model, output,
        execution_origin={'mode':'OWNER_MANUAL_LAUNCH', 'provider_job_id':None,
                          'provider_attestation':'UNAVAILABLE', 'launch_id':request['launch_id']})
    (Path(output)/'owner-launch.json').write_bytes(canonical_bytes(receipt))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--owner-launch-id',required=True)
    p.add_argument('--confirm-free-cpu',action='store_true')
    a=p.parse_args()
    launch(json.loads(a.request.read_bytes()),a.model,a.output,confirmation=a.owner_launch_id,
           free_cpu_confirmed=a.confirm_free_cpu)


if __name__=='__main__':main()
