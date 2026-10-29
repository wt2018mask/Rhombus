"""Finite-image soft clearance, explicitly approximate and unqualified."""
import numpy as np
from scipy.special import logsumexp


def soft_clearance(positions, image_positions, radii, beta, *, chunk_size=16):
    """Return soft minimum radius and gradient; singular at host centres.

    Caller supplies a fixed finite set of periodic images. Omitted images and
    image-set changes must be assessed separately; no exact periodicity claim.
    """
    x=np.asarray(positions,float);sites=np.asarray(image_positions,float);r=np.asarray(radii,float)
    if x.ndim!=2 or x.shape[1]!=3 or sites.ndim!=2 or sites.shape[1]!=3 or len(sites)!=len(r) or not len(r) or not np.isfinite(x).all() or not np.isfinite(sites).all() or not np.isfinite(r).all() or not np.isfinite(beta) or beta<=0 or chunk_size<1:
        raise ValueError('finite points, images, radii and beta required')
    values=[];gradients=[]
    for i in range(0,len(x),chunk_size):
        diff=x[i:i+chunk_size,None,:]-sites[None,:,:];distance=np.linalg.norm(diff,axis=2)
        if np.any(distance<1e-10):raise ValueError('clearance gradient singular at host center')
        gap=distance-r;logits=-beta*gap;logz=logsumexp(logits,axis=1);weights=np.exp(logits-logz[:,None]);values.append(-logz/beta);gradients.append(np.sum(weights[:,:,None]*diff/distance[:,:,None],axis=1))
    return np.concatenate(values),np.concatenate(gradients)
