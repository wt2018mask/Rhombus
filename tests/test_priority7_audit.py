import numpy as np
import pytest
from rhombus.transport.soft_clearance import soft_clearance

def test_soft_clearance_tie_gradient_and_lower_bound():
    sites=np.array([[-1.,0,0],[1.,0,0]]);radius=np.array([.2,.2]);p=np.array([[0.,.3,0.]])
    value,gradient=soft_clearance(p,sites,radius,30.)
    assert value[0] < np.sqrt(1.09)-.2
    assert gradient[0,0]==pytest.approx(0.,abs=1e-12)
    h=1e-5;num=(soft_clearance(p+[[0,h,0]],sites,radius,30.)[0]-soft_clearance(p-[[0,h,0]],sites,radius,30.)[0])/(2*h)
    assert gradient[0,1]==pytest.approx(num[0],abs=1e-8)
    with pytest.raises(ValueError):soft_clearance(sites[:1],sites,radius,30.)


def test_nested_bootstrap_refits_out_of_bag(monkeypatch):
    import importlib.util
    from pathlib import Path
    path=Path(__file__).parents[1]/'scripts/diagnostics/priority7_statistics.py'
    spec=importlib.util.spec_from_file_location('p7stats',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rows=[{'parent':str(i),'score':float(i),'label':int(i>=3)} for i in range(6)]
    seen=[];original=m.p6.choose_threshold
    def choose(x,y):seen.append((tuple(x),tuple(y)));return original(x,y)
    monkeypatch.setattr(m.p6,'choose_threshold',choose)
    result=m.nested_bootstrap(rows,'parent','score','label',iterations=100,seed=42)
    assert result['valid']>0 and len(seen)==result['valid']+result['skipped']['ONE_CLASS_TRAIN']
    assert result['accuracy_ci95'][0]<=result['accuracy_ci95'][1]


def test_adaptive_subdivision_and_minimax_tree():
    import importlib.util
    from pathlib import Path
    from pymatgen.core import Lattice
    path=Path(__file__).parents[1]/'scripts/diagnostics/priority7_network.py';spec=importlib.util.spec_from_file_location('p7net',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    p=m.adaptive_insert([[0,0,0],[.35,0,0]],.1)
    assert np.linalg.norm(np.diff(p,axis=0),axis=1).max()<=.1+1e-12
    field=np.zeros((3,3,3));lat=Lattice.cubic(3);e=lambda x:(np.zeros(len(x)),np.zeros_like(x))
    tree=m.minimax_tree(field,lat,e,np.zeros(3),.5,0);assert tree['dist'].max()==0
    assert np.allclose(m.tree_path(tree,7)[0],[0,0,0])


def test_joint_relax_preserves_common_junction_and_winding():
    import importlib.util
    from pathlib import Path
    p=Path(__file__).parents[1]/'scripts/diagnostics/priority7_joint.py';spec=importlib.util.spec_from_file_location('p7joint',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    paths=[np.array([[0.,0,0],[.5,.3,0],[1.,0,0]]),np.array([[0.,0,0],[.3,.5,0],[0.,1,0]])]
    def evaluator(p):return np.sum(p*p,axis=1),-2*p
    result,meta=m.joint_relax(paths,evaluator,max_iterations=3)
    np.testing.assert_allclose(result[0][0],result[1][0]);np.testing.assert_allclose(result[0][-1]-result[0][0],[1,0,0]);np.testing.assert_allclose(result[1][-1]-result[1][0],[0,1,0])
    assert 'success' in meta


def test_minimax_connector_accounts_for_edge_interiors():
    import importlib.util
    from pathlib import Path
    from pymatgen.core import Lattice
    path=Path(__file__).parents[1]/'scripts/diagnostics/priority7_network.py';spec=importlib.util.spec_from_file_location('p7net_edges',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    n=4;lat=Lattice.cubic(4)
    def e(x):return 1+np.sin(np.pi*x[:,0]),np.zeros_like(x)
    xyz=np.stack(np.meshgrid(*([np.arange(n)/n]*3),indexing='ij'),axis=-1)
    field=e(lat.get_cartesian_coords(xyz.reshape(-1,3)))[0].reshape((n,n,n))
    tree=m.minimax_tree(field,lat,e,np.zeros(3),.1,0)
    target=np.ravel_multi_index((1,0,0),field.shape)
    assert tree['dist'][target]>1.99


def test_joint_refine_inserts_short_edge_with_interior_spike():
    import importlib.util
    from pathlib import Path
    p=Path(__file__).parents[1]/'scripts/diagnostics/priority7_joint.py';spec=importlib.util.spec_from_file_location('p7refine',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    def e(x):return np.exp(-((x[:,0]-.025)/.005)**2),np.zeros_like(x)
    points,count=m.refine(np.array([[0.,0.,0.],[.05,0.,0.]]),e)
    assert count==1 and len(points)==3 and points[1,0]==pytest.approx(.025)
