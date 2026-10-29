import importlib.util
from pathlib import Path
import json
import numpy as np
import pytest

ROOT=Path(__file__).parents[1]
p=ROOT/'scripts/diagnostics/priority6_statistics.py'
s=importlib.util.spec_from_file_location('priority6_statistics',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_threshold_uses_training_and_undefined_classes():
    assert m.choose_threshold([1,2],[0,1])==pytest.approx(1.5)
    assert m.choose_threshold([1,2],[1,1]) is None
    assert m.metrics([1,2],[1,1])['auc'] is None

def test_stored_holdouts_exclude_each_held_group_and_validate_counts():
    x=json.loads((ROOT/'data/benchmarks/v3_static/priority6_statistics_v2.json').read_text())
    for key,entry in x['holdouts'].items():
        group='parent_id' if key.endswith('parent_id') else 'formula'
        for r in entry['predictions']:
            assert r[group]==r['group'] and r['training_n']>0
            original=json.loads((ROOT/'data/benchmarks/v3_static/priority4_grouped_v3.json').read_text())['rows']
            subset=[v for v in original if not key.startswith('1000_') or v['production_steps']==1000]
            assert r['training_n']==sum(v[group]!=r['group'] for v in subset)
    assert x['holdouts']['all_parent_id']['folds']==12
    assert x['holdouts']['all_formula']['folds']==16
    assert x['qualification']=='ABSTAIN'

def test_network_cycle_junction_and_winding_for_first_completed():
    f=ROOT/'data/benchmarks/v3_static/priority6_li2s_n16_o0_v1.json'
    x=json.loads(f.read_text());anchor=np.array(x['anchor_cartesian']);assert x['winding_rank']==3
    for r in x['paths']:
        pts=np.array(r['string']['points_cartesian']);np.testing.assert_allclose(pts[0],anchor,atol=1e-8)
        assert r['after']['winding_matches']
