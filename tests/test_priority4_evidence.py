import importlib.util
from pathlib import Path
import numpy as np
import pytest
p=Path(__file__).parents[1]/'scripts/diagnostics/priority4_evidence.py'
s=importlib.util.spec_from_file_location('priority4_evidence',p); m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

def test_auc_one_class_undefined_and_ties():
    assert m.metric([1,2],[.1,.2])['auc'] is None
    assert m.metric([1,1],[.1,1.])['auc']==pytest.approx(.5)

def test_paired_metric_comparison_is_invariant_to_order():
    x=np.array([1,2,3]);y=np.array([.2,.9,.4]);i=[2,0,1]
    assert m.metric(x,y)==m.metric(x[i],y[i])
