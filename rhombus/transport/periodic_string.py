"""Exploratory fixed-winding string relaxation on a caller-supplied force field."""
import numpy as np


def _redistribute(points):
    lengths=np.linalg.norm(np.diff(points,axis=0),axis=1);distance=np.r_[0.,np.cumsum(lengths)]
    if np.any(lengths<=1e-12):raise ValueError('string has coincident points')
    target=np.linspace(0,distance[-1],len(points))
    return np.column_stack([np.interp(target,distance,points[:,i]) for i in range(3)])


def relax_periodic_string(points, evaluate, *, max_iterations, force_tolerance_eV_A, step_scale, max_step_A):
    """Relax normal forces, redistribute arc length and retain endpoints.

    A converged sampled string is not a global MEP or 3D connectivity proof.
    """
    p=np.asarray(points,float).copy()
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<3 or not np.isfinite(p).all() or not isinstance(max_iterations,int) or max_iterations<1 or any(not np.isfinite(x) or x<=0 for x in (force_tolerance_eV_A,step_scale,max_step_A)):
        raise ValueError('finite string and explicit positive bounds required')
    ends=p[[0,-1]].copy();p=_redistribute(p);converged=False;last=None
    for iteration in range(max_iterations):
        energy,force=evaluate(p);energy=np.asarray(energy);force=np.asarray(force)
        if energy.shape!=(len(p),) or force.shape!=p.shape or not np.isfinite(energy).all() or not np.isfinite(force).all():raise ValueError('invalid energy or force')
        tangent=p[2:]-p[:-2];norm=np.linalg.norm(tangent,axis=1)
        if np.any(norm<=1e-12):raise ValueError('undefined string tangent')
        tangent/=norm[:,None]; projected=force[1:-1]-(force[1:-1]*tangent).sum(axis=1)[:,None]*tangent
        last=float(np.linalg.norm(projected,axis=1).max())
        if last<=force_tolerance_eV_A:converged=True;break
        update=step_scale*projected;scale=np.minimum(1.,max_step_A/np.maximum(np.linalg.norm(update,axis=1),1e-300));p[1:-1]+=update*scale[:,None];p=_redistribute(p);p[0],p[-1]=ends
    energy,force=evaluate(p);tangent=p[2:]-p[:-2];norm=np.linalg.norm(tangent,axis=1)
    if np.any(norm<=1e-12):raise ValueError('undefined final string tangent')
    tangent/=norm[:,None]; projected=force[1:-1]-(force[1:-1]*tangent).sum(axis=1)[:,None]*tangent
    last=float(np.linalg.norm(projected,axis=1).max());converged=last<=force_tolerance_eV_A
    return {'points_cartesian':p.tolist(),'max_sampled_energy_eV':float(np.max(energy)),'max_perpendicular_force_eV_A':last,
            'converged':bool(converged),'iterations':iteration+1,'winding_displacement_cartesian':(ends[1]-ends[0]).tolist(),
            'scope':'SAMPLED_STRING_NOT_GLOBAL_3D_CONNECTIVITY','qualification':'ABSTAIN'}
