"""Periodic Morse/site-energy research model and exact voxel-graph thresholds.

Caller parameters are not independently calibrated BVSE parameters. Discrete
graph exactness does not imply continuum convergence or physical validity.
"""
from itertools import product
from collections import deque
import numpy as np
from scipy.special import erfc


class SiteEnergyEvaluator:
    """Morse anion wells + screened Coulomb/Pauli cation repulsion, eV/Angstrom.

    anions maps symbol -> (R0_A, b_A, D_eV); cations maps symbol ->
    (formal_charge, screening_A, exclusion_A). All nonmobile sites need a map.
    """
    def __init__(self, structure, *, anions, cations, mobile_species='Li', pauli=True):
        if not structure.is_ordered: raise ValueError('ordered host required')
        self.lattice=structure.lattice
        self.pauli=bool(pauli)
        self.sites=[s for s in structure if s.specie.symbol!=mobile_species]
        self.parameters=[]
        for site in self.sites:
            symbol=site.specie.symbol
            if symbol in anions:
                kind,params='morse',anions[symbol]
            elif symbol in cations:
                kind,params='repulsion',cations[symbol]
            else: raise ValueError('missing explicit host parameters: '+symbol)
            if len(params)!=3 or not np.isfinite(params).all() or min(params)<=0:
                raise ValueError('positive finite parameter triples required')
            self.parameters.append((kind,tuple(params)))
        if not self.sites:raise ValueError('host is empty')

    def __call__(self, positions):
        from pymatgen.util.coord import pbc_shortest_vectors
        x=np.asarray(positions,float)
        if x.ndim!=2 or x.shape[1]!=3 or not np.isfinite(x).all():raise ValueError('finite Cartesian Nx3 required')
        vectors=pbc_shortest_vectors(self.lattice,self.lattice.get_fractional_coords(x),[s.frac_coords for s in self.sites])
        r=np.maximum(np.linalg.norm(vectors,axis=2),1e-6)
        energy=np.zeros(len(x)); force=np.zeros_like(x)
        for j,(kind,params) in enumerate(self.parameters):
            d=r[:,j]
            if kind=='morse':
                r0,b,depth=params
                exp=np.exp(np.clip((r0-d)/b,-100,100))
                e=depth*(exp*exp-2*exp)
                derivative=2*depth*(exp-exp*exp)/b
            else:
                charge,rho,rmin=params
                c=14.3996454784255*charge
                e=c*erfc(d/rho)/d
                derivative=c*(-2*np.exp(-(d/rho)**2)/(np.sqrt(np.pi)*rho*d)-erfc(d/rho)/d**2)
                if self.pauli:
                    e+=(rmin/d)**12
                    derivative-=12*rmin**12/d**13
            energy+=e; force+=derivative[:,None]*vectors[:,j]/d[:,None]
        return energy,force

    def grid(self, spacing_A=.28, *, min_dimension=24, max_dimension=40):
        if not np.isfinite(spacing_A) or spacing_A<=0 or not 2<=min_dimension<=max_dimension<=40:
            raise ValueError('invalid bounded grid')
        shape=np.clip(np.ceil(np.array(self.lattice.abc)/spacing_A).astype(int),min_dimension,max_dimension)
        frac=np.stack(np.meshgrid(*[np.arange(n)/n for n in shape],indexing='ij'),axis=-1)
        values,_=self(self.lattice.get_cartesian_coords(frac.reshape(-1,3)))
        return values.reshape(tuple(shape))


def percolation_thresholds(field, *, lattice=None, host_fractional=None, host_radii_A=None):
    """26-neighbor periodic union-find with integer image potentials and cycle rank.

    Each rank must occur within ONE connected component. Thresholds reference
    the global minimum; disconnected local cages do not imply a low barrier.
    """
    values=np.asarray(field,float)
    if values.ndim!=3 or min(values.shape)<2 or values.size>64000 or not np.isfinite(values).all():
        raise ValueError('finite 3D field of at most 40^3 voxels required')
    shape=np.array(values.shape); n=values.size
    geometry=(lattice,host_fractional,host_radii_A)
    if any(v is not None for v in geometry) and not all(v is not None for v in geometry):
        raise ValueError('lattice, host coordinates and explicit ionic radii required together')
    if lattice is not None:
        host_fractional=np.asarray(host_fractional,float);host_radii_A=np.asarray(host_radii_A,float)
        if (host_fractional.ndim!=2 or host_fractional.shape[1]!=3 or not len(host_fractional)
            or host_radii_A.shape!=(len(host_fractional),) or not np.isfinite(host_fractional).all()
            or not np.isfinite(host_radii_A).all() or (host_radii_A<0).any()):
            raise ValueError('finite host coordinates and nonnegative radii required')
    parent=np.arange(n); size=np.ones(n,int); offset=np.zeros((n,3),int); active=np.zeros(n,bool)
    bases=[[] for _ in range(n)]; thresholds=[None]*3; witnesses=[None]*3
    forest=[[] for _ in range(n)]
    def find(a):
        if parent[a]!=a:
            p=parent[a]; root,delta=find(p);offset[a]+=delta;parent[a]=root
        return parent[a],offset[a].copy()
    def add_basis(root,vector,edge):
        if not np.any(vector) or len(bases[root])==3:return
        vectors=[v for v,_ in bases[root]]+[vector.tolist()]
        if np.linalg.matrix_rank(np.array(vectors,float))>len(bases[root]):bases[root].append((vector.tolist(),edge))
    neighbors=[np.array(v) for v in product((-1,0,1),repeat=3) if v!=(0,0,0)]
    flat=values.ravel(); minimum=float(flat.min())
    for a in np.argsort(flat,kind='stable'):
        active[a]=True; cell=np.array(np.unravel_index(a,values.shape))
        for step in neighbors:
            raw=cell+step; wrapped=raw%shape; image=raw//shape
            b=np.ravel_multi_index(tuple(wrapped),values.shape)
            if not active[b]:continue
            ra,pa=find(a); rb,pb=find(b); delta=pa+image-pb
            if ra==rb:add_basis(ra,delta,(int(a),int(b),image.copy()))
            else:
                forest[a].append((int(b),image.copy()));forest[b].append((int(a),-image.copy()))
                if size[ra]<size[rb]:ra,rb=rb,ra;delta=-delta
                parent[rb]=ra;offset[rb]=delta;size[ra]+=size[rb]
                for v,edge in bases[rb]:add_basis(ra,np.array(v),edge)
            for k in range(len(bases[ra])):
                if thresholds[k] is None:
                    thresholds[k]=float(flat[a]-minimum);witnesses[k]=list(bases[ra][:k+1])
        if thresholds[2] is not None:break
    def reconstruct(edge):
        a,b,closing_image=edge
        # The union edges form a forest, so later merges cannot alter this path.
        previous={a:(None,np.zeros(3,int))};queue=deque([a])
        while queue and b not in previous:
            node=queue.popleft()
            for other,image in forest[node]:
                if other not in previous:
                    previous[other]=(node,image);queue.append(other)
        nodes=[];images=[];node=b
        while node is not None:
            nodes.append(node);prior,image=previous[node];images.append(image);node=prior
        nodes.reverse();images.reverse();unwrapped=[];translation=np.zeros(3,int)
        for node,image in zip(nodes,images):
            translation+=image
            unwrapped.append((np.array(np.unravel_index(node,values.shape))/shape+translation).tolist())
        translation-=closing_image
        unwrapped.append((np.array(np.unravel_index(a,values.shape))/shape+translation).tolist())
        result={'fractional_path':unwrapped,'winding_vector':translation.tolist(),
                'maximum_energy_eV':float(flat[nodes].max()),'bottleneck_radius_A':None}
        if lattice is not None:
            from pymatgen.util.coord import pbc_shortest_vectors
            # Radius is a voxel-sampled clearance on this witness, NOT the
            # maximum-clearance path or a continuous saddle estimate.
            distances=np.linalg.norm(pbc_shortest_vectors(lattice,unwrapped,host_fractional),axis=2)
            result['bottleneck_radius_A']=float(np.min(distances-host_radii_A[None,:]))
        return result
    cycles={str(rank+1)+'D':[reconstruct(edge) for _,edge in basis] for rank,basis in enumerate(witnesses) if basis}
    radius=(min(c['bottleneck_radius_A'] for c in cycles['3D']) if lattice is not None and '3D' in cycles else None)
    return {'schema_version':'rhombus-voxel-minimax-v1','grid_shape':list(values.shape),
            'minimum_energy_eV':minimum,'barriers_eV':dict(zip(('1D','2D','3D'),thresholds)),
            'percolating_cycles':cycles,'bottleneck_radius_A':radius,
            'bottleneck_status':'VOXEL_WITNESS_CLEARANCE' if radius is not None else 'HOST_RADII_NOT_SUPPLIED',
            'graph_neighborhood':26,'calibration_status':'UNQUALIFIED','qualification':'ABSTAIN'}
