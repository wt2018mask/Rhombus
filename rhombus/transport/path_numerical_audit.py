"""Independent segment and winding diagnostics. No qualification decisions."""
import numpy as np
from pymatgen.util.coord import pbc_shortest_vectors


def inspect_witness(path_frac, winding, lattice, evaluate, host_frac, radii, *, max_spacing_A):
    p = np.asarray(path_frac, float); winding = np.asarray(winding, int); shape = np.asarray(host_frac, float); radii = np.asarray(radii, float)
    if p.ndim != 2 or p.shape[1] != 3 or len(p)<2 or not np.isfinite(p).all() or winding.shape != (3,) or not np.isfinite(max_spacing_A) or max_spacing_A <= 0:
        raise ValueError('invalid witness or spacing')
    if shape.ndim != 2 or shape.shape[1] != 3 or len(shape)!=len(radii) or not len(shape): raise ValueError('invalid host geometry')
    lengths = np.linalg.norm(lattice.get_cartesian_coords(np.diff(p,axis=0)),axis=1)
    ratio = lengths / max_spacing_A
    ratio = np.where(np.isclose(ratio, np.rint(ratio), rtol=1e-12, atol=1e-12), np.rint(ratio), ratio)
    count = np.maximum(1, np.ceil(ratio).astype(int))
    samples = np.concatenate([a+(b-a)*np.arange(n)[:,None]/n for a,b,n in zip(p[:-1],p[1:],count)]+[p[-1:]])
    coords = lattice.get_cartesian_coords(samples); energies = np.asarray(evaluate(coords)[0]); ve = np.asarray(evaluate(lattice.get_cartesian_coords(p))[0])
    clear = np.concatenate([(np.linalg.norm(pbc_shortest_vectors(lattice,samples[i:i+128],shape),axis=2)-radii).min(axis=1) for i in range(0,len(samples),128)])
    delta=p[-1]-p[0]
    return {'winding':winding.tolist(), 'endpoint_delta':delta.tolist(), 'winding_matches':bool(np.allclose(delta,winding,atol=1e-9)),
            'vertex_max_eV':float(ve.max()),'sampled_max_eV':float(energies.max()),'missed_barrier_eV':float(energies.max()-ve.max()),
            'sampled_min_clearance_A':float(clear.min()),'segment_count':len(lengths),'max_segment_length_A':float(lengths.max()),
            'max_sample_spacing_A':float(max_spacing_A),'sample_count':len(samples), 'steric_overlap_sampled':bool(clear.min()<0)}
