"""Conservative finite-image periodic nearest-surface clearance certificates."""
from itertools import product
import numpy as np


def complete_images(lattice, host_fractional, radii, *, margin_A=0., max_images=1000000):
    """Bound omitted images for *all* wrapped fractional query positions.

    For wrapped q and host f, a trial image has Cartesian displacement at most
    half the sum of lattice-vector lengths. For |n_i| >= K_i+1, the reciprocal
    plane inequality gives distance >= K_i*h_i.  Thus K_i*h_i-r_max > U+margin
    excludes all omitted images. This certifies a nearest surface, not the
    infinite-image softmin tail. Floating arithmetic is not interval arithmetic.
    """
    matrix=np.asarray(lattice.matrix,float); frac=np.asarray(host_fractional,float);r=np.asarray(radii,float)
    if frac.ndim!=2 or frac.shape[1]!=3 or not len(frac) or r.shape!=(len(frac),) or not np.isfinite(frac).all() or not np.isfinite(r).all() or (r<0).any() or not np.isfinite(margin_A) or margin_A<0:
        raise ValueError('finite host geometry and nonnegative margin required')
    frac=frac%1;heights=1/np.linalg.norm(np.linalg.inv(matrix),axis=0)
    upper=.5*np.linalg.norm(matrix,axis=1).sum()-float(r.max())
    # One fixed largest-radius host gives this upper bound for every query.
    k=np.maximum(1,np.floor((upper+r.max()+margin_A)/heights).astype(int)+1)
    lower=k*heights-r.max();verified=bool(np.all(lower>upper+margin_A))
    count=int(np.prod(2*k+1))*len(frac)
    metadata={'shell_half_width':k.tolist(),'image_shell_shape':(2*k+1).tolist(),'plane_heights_A':heights.tolist(),'upper_bound_A':float(upper),'omitted_surface_lower_bounds_A':lower.tolist(),'margin_A':margin_A,'periodic_image_completeness_verified':verified and count<=max_images,'image_count':count,'scope':'EXACT_NEAREST_SURFACE_BOUND_NOT_SOFTMIN_TAIL_FLOAT64'}
    if count>max_images:return None,None,metadata
    shifts=np.asarray(list(product(*[range(-v,v+1) for v in k])))
    xyz=lattice.get_cartesian_coords((frac[None,:,:]+shifts[:,None,:]).reshape(-1,3))
    return xyz,np.tile(r,len(shifts)),metadata


def periodic_clearance(points,lattice,images,radii,*,chunk_size=64):
    x=np.asarray(points,float);out=[]
    for i in range(0,len(x),chunk_size):
        wrapped=lattice.get_cartesian_coords(lattice.get_fractional_coords(x[i:i+chunk_size])%1)
        out.append((np.linalg.norm(wrapped[:,None,:]-images[None,:,:],axis=2)-radii).min(axis=1))
    return np.concatenate(out)


def sampled_lipschitz_bound(points,lattice,images,radii,*,max_spacing_A=.025):
    """One-witness lower bound from 1-Lipschitz exact periodic clearance."""
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<2 or not np.isfinite(p).all() or not np.isfinite(max_spacing_A) or max_spacing_A<=0:raise ValueError('finite path and positive spacing required')
    samples=[]
    for a,b in zip(p[:-1],p[1:]):
        n=max(1,int(np.ceil(np.linalg.norm(b-a)/max_spacing_A)));samples.extend(a+(b-a)*np.arange(n)[:,None]/n)
    samples=np.vstack([samples,p[-1]]);values=periodic_clearance(samples,lattice,images,radii);lengths=np.linalg.norm(np.diff(samples,axis=0),axis=1)
    lower=np.minimum(values[:-1],values[1:])-lengths/2
    return {'sampled_min_clearance_A':float(values.min()),'lower_bound_A':float(lower.min()),'samples':len(samples),'max_sample_spacing_A':float(lengths.max()),'scope':'ONE_WITNESS_1_LIPSCHITZ_FLOAT64_NOT_NETWORK_OPTIMUM'}
