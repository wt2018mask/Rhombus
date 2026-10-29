"""Bounded analytical tests using the actual graph, joint and clearance kernels."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import numpy as np
from pymatgen.core import Lattice
from rhombus.transport.segment_percolation import segment_percolation
from rhombus.transport.periodic_clearance import complete_images,periodic_clearance,sampled_lipschitz_bound
from rhombus.transport.soft_clearance import soft_clearance
from rhombus.transport.periodic_string import relax_periodic_string
from scripts.diagnostics.priority7_joint import joint_relax

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise FileExistsError('refuse overwrite')
 started=time.monotonic();rows=[];lat=Lattice.cubic(5.);amps=np.array([.2,.35,.5]);cell=4.;sc=Lattice.cubic(cell);images,rad,complete=complete_images(sc,[[0,0,0]],[1.2],margin_A=.025)
 def cosine(x):
  t=2*np.pi*x/5;return ((1-np.cos(t))*amps).sum(axis=1),-(2*np.pi/5)*np.sin(t)*amps
 def clearance(x):return -periodic_clearance(x,sc,images,rad),np.zeros_like(x)
 for n in (16,20,24):
  for origin in ((0.,0.,0.),(.13,.29,.41)):
   shift=np.array(origin)/n;axis=np.arange(n)/n;f=np.stack(np.meshgrid(axis,axis,axis,indexing='ij'),axis=-1).reshape(-1,3)+shift
   ce=cosine(lat.get_cartesian_coords(f))[0].reshape((n,)*3);cg=segment_percolation(ce,lat,cosine,origin=shift,max_spacing_A=.2)
   se=clearance(sc.get_cartesian_coords(f))[0].reshape((n,)*3);sg=segment_percolation(se,sc,clearance,origin=shift,max_spacing_A=.2)
   cycle=cg['cycles_3d'][0];pts=lat.get_cartesian_coords(cycle['fractional_path']);optim,info=joint_relax([pts],cosine,max_iterations=5);co_peak=float(np.max(cosine(optim[0])[0]));
   g=sg['cycles_3d'][0];cp=sc.get_cartesian_coords(g['fractional_path']);
   def soft(x):
    w=sc.get_cartesian_coords(sc.get_fractional_coords(x)%1);v,grad=soft_clearance(w,images,rad,30.);return -v,grad
   opt=relax_periodic_string(cp,soft,max_iterations=5,force_tolerance_eV_A=.05,step_scale=.01,max_step_A=.05);bounds=sampled_lipschitz_bound(np.asarray(opt['points_cartesian']),sc,images,rad)
   final_points=np.asarray(opt['points_cartesian']);witness_vertices=periodic_clearance(final_points,sc,images,rad);witness_hash=hashlib.sha256(final_points.astype('<f8').tobytes()).hexdigest()
   if bounds['lower_bound_A']>bounds['sampled_min_clearance_A']+1e-12:raise ValueError('same-witness clearance bound violation')
   radius=-sg['thresholds_eV']['3D'];rows.append({'n':n,'origin_voxel':list(origin),'cosine_graph_barrier_eV':cg['barrier_3d_eV'],'cosine_voxel_reference_eV':cg['minimum_energy_eV'],'cosine_absolute_saddle_eV':cg['thresholds_eV']['3D'],'cosine_error_eV':cg['barrier_3d_eV']-1.,'cosine_absolute_saddle_error_eV':cg['thresholds_eV']['3D']-1.,'cosine_joint_witness_peak_eV':co_peak,'cosine_joint_optimizer':info,'cosine_rank':int(np.linalg.matrix_rank([v['winding_vector'] for v in cg['cycles_3d']])), 'sc_graph_radius_A':radius,'sc_error_A':radius-(np.sqrt(2)*2-1.2),'sc_clearance_string_converged':opt['converged'],'sc_witness':{**bounds,'witness_sha256':witness_hash,'points_cartesian':final_points.tolist(),'vertex_min_clearance_A':float(witness_vertices.min()),'sampled_error_A':bounds['sampled_min_clearance_A']-(2*np.sqrt(2)-1.2),'lower_bound_error_A':bounds['lower_bound_A']-(2*np.sqrt(2)-1.2)},'sc_graph_scope':'PRE_OPTIMIZATION_DISCRETE_NETWORK'})
   print('completed',n,origin,flush=True)
 bcc=Lattice.cubic(4);bi,br,bmeta=complete_images(bcc,[[0,0,0],[.5,.5,.5]],[1.2,1.2]);point=np.array([[1.5,1.5,0.]]);tied=np.array([[0,0,0],[2,2,2],[2,2,-2]]);d=np.linalg.norm(point-tied,axis=1);grad3=np.mean((point-tied)/d[:,None],axis=0);v,grad=soft_clearance(point,bi,br,30);h=1e-5;num=np.array([(soft_clearance(point+np.eye(3)[i]*h,bi,br,30)[0][0]-soft_clearance(point-np.eye(3)[i]*h,bi,br,30)[0][0])/(2*h) for i in range(3)]);tangent=np.array([-1,1,0])/np.sqrt(2)
 out={'schema':'priority7-r1-analytical-v1','driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'code_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['rhombus/transport/segment_percolation.py','rhombus/transport/periodic_clearance.py','rhombus/transport/soft_clearance.py','rhombus/transport/periodic_string.py','scripts/diagnostics/priority7_joint.py']},'references':{'cosine_rank3_eV':1.,'sc_rank3_clearance_A':float(2*np.sqrt(2)-1.2)},'rows':rows,'sc_image_completeness':complete,'bcc':{'label':'LOCAL_VORONOI_TIE_DIAGNOSTIC','tied_distances_A':d.tolist(),'three_neighbor_gradient':grad3.tolist(),'finite_image_softmin_A':float(v[0]),'finite_image_gradient':grad[0].tolist(),'finite_difference_gradient':num.tolist(),'tangent_projection':float(grad[0]@tangent),'image_count':len(bi),'image_completeness':bmeta},'qualification':'ABSTAIN','seconds':time.monotonic()-started};a.output.write_text(json.dumps(out,sort_keys=True,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':main()
