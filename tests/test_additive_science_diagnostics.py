import copy
import json
import subprocess
from pathlib import Path
from urllib.error import URLError
import numpy as np
import pytest
from rhombus.transport.window_diagnostics import thermal_windows, multi_origin_msd
from rhombus.transport.static_channels import StaticChannelScreener
from rhombus.domain.profiles import PROFILES
from scripts.science.source_outage import record_timeout


def test_compaction_preserves_effective_state_and_rejects_tamper():
    from scripts.development import continuity as c
    root=Path(__file__).resolve().parents[1]
    previous=json.loads(subprocess.check_output(['git','show','967e824c7146e050c1eeca142f0c2d29d2b54b46:data/development/CURRENT.json'],cwd=root))
    current=json.loads(c.CURRENT.read_bytes()); actual=c.resolve_state(current); actual.pop('continuation')
    assert actual==c.resolve_state(previous)
    assert c.CURRENT.stat().st_size<=3200
    bad=copy.deepcopy(current); bad['continuation']['sha256']='0'*64
    with pytest.raises(ValueError,match='SHA-256'):c.resolve_state(bad)


def test_window_excludes_warmup_without_qualifying_physics():
    trace={'atom_count':2,'samples':[{'phase':'equil','time_fs':-1,'temperature_K':0,'potential_energy_eV':999,'kinetic_energy_eV':0}]}
    trace['samples'] += [{'phase':'production','time_fs':i*1000,'temperature_K':550.,'potential_energy_eV':2.,'kinetic_energy_eV':.1} for i in range(10)]
    result=thermal_windows(trace)
    assert result['mean_temp_k']==550 and abs(result['post_eq_potential_drift_ev_per_atom_ps'])<1e-12
    assert result['qualification']=='ABSTAIN' and result['kinetic_temperature_K'] is None


def test_multi_origin_removes_rigid_host_drift_and_detects_deformation():
    rng=np.random.default_rng(42); n=256
    mobile=np.cumsum(rng.normal(size=(n,16,3)),axis=0)
    host=np.zeros((n,2,3)); times=np.arange(n)*.1
    first=multi_origin_msd(mobile,host,times,host_limit_angstrom=.5)
    drift=np.arange(n)[:,None,None]*np.array([.1,.2,.3])
    second=multi_origin_msd(mobile+drift,host+drift,times,host_limit_angstrom=.5)
    assert second['beta']==pytest.approx(first['beta'])
    assert second['msd_A2']==pytest.approx(first['msd_A2'])
    host[:,0,0]=np.linspace(0,5,n)
    assert multi_origin_msd(mobile,host,times,host_limit_angstrom=.5)['regime']=='FRAMEWORK_INSTABILITY'
    with pytest.raises(ValueError):multi_origin_msd(mobile,host,times[::-1],host_limit_angstrom=.5)


def test_diffusive_and_caged_synthetic_controls_do_not_qualify_transport():
    rng=np.random.default_rng(19); n=512; host=np.zeros((n,4,3)); t=np.arange(n)*.1
    walk=np.cumsum(rng.normal(size=(n,64,3)),axis=0)
    diff=multi_origin_msd(walk,host,t,host_limit_angstrom=.5)
    assert .85<=diff['beta']<=1.15 and diff['regime']=='DIFFUSIVE_FICKIAN'
    cage=multi_origin_msd(rng.normal(scale=.05,size=(n,64,3)),host,t,host_limit_angstrom=.5)
    assert cage['regime']=='VIBRATIONAL_CAGED'
    assert diff['qualification']==cage['qualification']=='ABSTAIN'


def test_periodic_graph_and_partial_occupancy_are_diagnostics():
    from pymatgen.core import Structure,Lattice
    screen=StaticChannelScreener()
    for lengths,rank in [([3,3,3],3),([3,3,10],2),([3,10,10],1),([10,10,10],0)]:
        s=Structure(Lattice.orthorhombic(*lengths),['Li'],[[0,0,0]])
        result=screen.analyze(s,cutoff_angstrom=3.1)
        assert result['occupied_site_periodic_rank']==rank
        assert not result['candidate_falsified'] and not result['execution_authorized']
    disorder=Structure(Lattice.cubic(4),[{'Li':.5}],[[0,0,0]])
    assert screen.analyze(disorder)['verdict']=='DISORDERED_REQUIRES_ORDERING'
    assert all(p.qualification=='ABSTAIN' for p in PROFILES.values())


def test_timeout_receipt_has_no_fabricated_digest(tmp_path):
    assert record_timeout(URLError(TimeoutError()),tmp_path/'failure',resources=['https://example.invalid'])
    report=json.loads((tmp_path/'failure/source-unavailable.json').read_text())
    assert report['sha256'] is None and not report['scientific_GO']
    assert not record_timeout(ValueError('checksum'),tmp_path/'other',resources=[])
    assert record_timeout(URLError('timed out'),tmp_path/'string-timeout',resources=[])
