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
    def __init__(self, structure, *, anions, cations, mobile_species='Li', pauli=True,
                 shell_stiffness=None, shell_max_A=.15, periodic_cutoff_A=None,
                 born_mayer=None, unscreened_contacts=None):
        if not structure.is_ordered: raise ValueError('ordered host required')
        self.lattice=structure.lattice
        self.pauli=bool(pauli)
        self.shell_stiffness={} if shell_stiffness is None else dict(shell_stiffness)
        if not np.isfinite(shell_max_A) or not 0<=shell_max_A<=.2 or any(not np.isfinite(k) or k<=0 for k in self.shell_stiffness.values()):
            raise ValueError('finite positive shell stiffness and displacement in [0,.2] required')
        self.shell_max_A=shell_max_A
        self.periodic_cutoff_A=periodic_cutoff_A
        self.born_mayer={} if born_mayer is None else dict(born_mayer)
        self.unscreened_contacts={} if unscreened_contacts is None else dict(unscreened_contacts)
        for triple in self.born_mayer.values():
            if len(triple)!=3 or any(not np.isfinite(v) or v<=0 for v in triple):raise ValueError('positive Born-Mayer parameters required')
        if any(not np.isfinite(v) or v<=0 for v in self.unscreened_contacts.values()):raise ValueError('positive contact radii required')
        if periodic_cutoff_A is not None and (not np.isfinite(periodic_cutoff_A) or not 4<=periodic_cutoff_A<=12):
            raise ValueError('bounded periodic cutoff required')
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
        groups={};self.site_group_indices=[]
        for site,(kind,params) in zip(self.sites,self.parameters):
            key=(kind,params,site.specie.symbol)
            if key not in groups:groups[key]=len(groups)
            self.site_group_indices.append(groups[key])
        self.parameter_groups=list(groups)
        self.site_group_indices=np.array(self.site_group_indices)
        if periodic_cutoff_A is not None:
            from scipy.spatial import cKDTree
            heights=1/np.linalg.norm(self.lattice.reciprocal_lattice_crystallographic.matrix,axis=1)
            count=np.ceil(periodic_cutoff_A/heights).astype(int)+1
            if np.prod(2*count+1)*len(self.sites)>1000000:raise ValueError('periodic image budget exceeded')
            shifts=np.array(list(product(*[range(-v,v+1) for v in count])))
            self.image_positions=(np.array([s.coords for s in self.sites])[None,:,:]
                                  +self.lattice.get_cartesian_coords(shifts)[:,None,:]).reshape(-1,3)
            self.image_site_indices=np.tile(np.arange(len(self.sites)),len(shifts))
            self.image_tree=cKDTree(self.image_positions)

    def _pair(self,kind,params,d,symbol):
        if kind=='morse':
            r0,b,depth=params;displacement=np.zeros_like(d)
            if symbol in self.shell_stiffness:
                k=self.shell_stiffness[symbol];mask=d<(3.2 if symbol in self.born_mayer else min(r0,3.2))
                lo=np.zeros(mask.sum());hi=(np.full(mask.sum(),self.shell_max_A) if symbol in self.born_mayer else np.minimum(self.shell_max_A,np.maximum(0,r0-d[mask])))
                for _ in range(32):
                    mid=(lo+hi)/2;a=np.exp(np.clip((r0-d[mask]-mid)/b,-100,100))
                    slope=2*depth*(a-a*a)/b+k*mid
                    if symbol in self.born_mayer:
                        amplitude,contact,rho=self.born_mayer[symbol]
                        slope-=amplitude*np.exp(np.clip((contact-d[mask]-mid)/rho,-100,100))/rho
                    lo=np.where(slope<0,mid,lo);hi=np.where(slope>=0,mid,hi)
                displacement[mask]=(lo+hi)/2
            exp=np.exp(np.clip((r0-d-displacement)/b,-100,100))
            e=depth*(exp*exp-2*exp)
            if symbol in self.shell_stiffness:e+=.5*self.shell_stiffness[symbol]*displacement**2
            derivative=2*depth*(exp-exp*exp)/b
        else:
            charge,rho,rmin=params;c=14.3996454784255*charge
            e=c*erfc(d/rho)/d
            derivative=c*(-2*np.exp(-(d/rho)**2)/(np.sqrt(np.pi)*rho*d)-erfc(d/rho)/d**2)
            if self.pauli:
                e+=(rmin/d)**12;derivative-=12*rmin**12/d**13
            if symbol in self.unscreened_contacts:
                contact=self.unscreened_contacts[symbol];u=np.clip(1-d/contact,0,1)
                correction=c*(1-erfc(d/rho))/d
                slope=c*(2*np.exp(-(d/rho)**2)/(np.sqrt(np.pi)*rho*d)-(1-erfc(d/rho))/d**2)
                e+=correction*u**4;derivative+=slope*u**4-correction*4*u**3/contact
        if symbol in self.born_mayer:
            amplitude,contact,rho=self.born_mayer[symbol]
            distance=d+displacement if kind=='morse' else d
            repulsion=amplitude*np.exp(np.clip((contact-distance)/rho,-100,100))
            e+=repulsion;derivative-=repulsion/rho
        return e,derivative

    def __call__(self, positions):
        from pymatgen.util.coord import pbc_shortest_vectors
        x=np.asarray(positions,float)
        if x.ndim!=2 or x.shape[1]!=3 or not np.isfinite(x).all():raise ValueError('finite Cartesian Nx3 required')
        if self.periodic_cutoff_A is not None:
            from scipy.spatial import cKDTree
            wrapped=self.lattice.get_cartesian_coords(self.lattice.get_fractional_coords(x)%1)
            pairs=self.image_tree.sparse_distance_matrix(cKDTree(wrapped),self.periodic_cutoff_A,output_type='coo_matrix')
            energy=np.zeros(len(x));force=np.zeros_like(x)
            pair_groups=self.site_group_indices[self.image_site_indices[pairs.row]]
            for j,(kind,params,symbol) in enumerate(self.parameter_groups):
                mask=pair_groups==j
                indices=pairs.col[mask];rows=pairs.row[mask];d=np.maximum(pairs.data[mask],1e-6)
                e,derivative=self._pair(kind,params,d,symbol)
                t=np.clip(d-(self.periodic_cutoff_A-1),0,1)
                switch=1-10*t**3+15*t**4-6*t**5;ds=-30*t*t*(1-t)**2
                derivative=derivative*switch+e*ds;e=e*switch
                np.add.at(energy,indices,e)
                np.add.at(force,indices,derivative[:,None]*(self.image_positions[rows]-wrapped[indices])/d[:,None])
            return energy,force
        vectors=pbc_shortest_vectors(self.lattice,self.lattice.get_fractional_coords(x),[s.frac_coords for s in self.sites])
        r=np.maximum(np.linalg.norm(vectors,axis=2),1e-6)
        energy=np.zeros(len(x)); force=np.zeros_like(x)
        for j,(kind,params) in enumerate(self.parameters):
            d=r[:,j]
            e,derivative=self._pair(kind,params,d,self.sites[j].specie.symbol)
            energy+=e; force+=derivative[:,None]*vectors[:,j]/d[:,None]
        return energy,force

    def grid(self, spacing_A=.28, *, min_dimension=24, max_dimension=40):
        if not np.isfinite(spacing_A) or spacing_A<=0 or not 2<=min_dimension<=max_dimension<=64:
            raise ValueError('invalid bounded grid')
        shape=np.clip(np.ceil(np.array(self.lattice.abc)/spacing_A).astype(int),min_dimension,max_dimension)
        frac=np.stack(np.meshgrid(*[np.arange(n)/n for n in shape],indexing='ij'),axis=-1)
        points=self.lattice.get_cartesian_coords(frac.reshape(-1,3))
        values=np.concatenate([self(points[i:i+2048])[0] for i in range(0,len(points),2048)])
        return values.reshape(tuple(shape))


class SpectatorSiteEnergyEvaluator:
    """One active Li, fixed N-1 Li spectators; no many-body Frenkel energy claim."""
    def __init__(self, structure, active_index, host_evaluator, *, screening_A=1.52, exclusion_A=1.52, periodic_cutoff_A=None, charge_product=1.):
        if (type(active_index) is not int or not 0<=active_index<len(structure)
            or structure[active_index].specie.symbol!='Li'
            or any(not np.isfinite(v) or v<=0 for v in (screening_A,exclusion_A))):
            raise ValueError('active Li index and positive spectator parameters required')
        self.host=host_evaluator;self.lattice=structure.lattice
        self.spectators=[s.frac_coords for i,s in enumerate(structure) if i!=active_index and s.specie.symbol=='Li']
        if not np.isfinite(charge_product) or charge_product<=0:raise ValueError('positive spectator charge product required')
        self.screening_A,self.exclusion_A=screening_A,exclusion_A
        self.charge_product=charge_product
        self.periodic_repulsion=None
        if self.spectators and periodic_cutoff_A is not None:
            from pymatgen.core import Structure
            only_spectators=Structure(self.lattice,['Li']*len(self.spectators),self.spectators)
            self.periodic_repulsion=SiteEnergyEvaluator(only_spectators,anions={},cations={'Li':(charge_product,screening_A,exclusion_A)},
                                                        mobile_species='_NONE',periodic_cutoff_A=periodic_cutoff_A)

    def __call__(self, positions):
        from pymatgen.util.coord import pbc_shortest_vectors
        x=np.asarray(positions,float);energy,force=self.host(x)
        if self.periodic_repulsion is not None:
            repulsion,repulsive_force=self.periodic_repulsion(x)
            return energy+repulsion,force+repulsive_force
        if self.spectators:
            vectors=pbc_shortest_vectors(self.lattice,self.lattice.get_fractional_coords(x),self.spectators)
            r=np.maximum(np.linalg.norm(vectors,axis=2),1e-6);rho=self.screening_A;rm=self.exclusion_A
            energy+=np.sum(14.3996454784255*self.charge_product*erfc(r/rho)/r+(rm/r)**12,axis=1)
            derivative=14.3996454784255*self.charge_product*(-2*np.exp(-(r/rho)**2)/(np.sqrt(np.pi)*rho*r)-erfc(r/rho)/r**2)-12*rm**12/r**13
            force+=np.sum(derivative[:,:,None]*vectors/r[:,:,None],axis=1)
        return energy,force

    grid=SiteEnergyEvaluator.grid


def refine_channel_barrier(field, lattice, evaluator, *, max_steps=600):
    """Sub-voxel analytic-force relaxation of the three graph winding witnesses.

    Global grid minimum is locally minimized independently. A nonconverged
    band remains nonconverged; refinement never guarantees mesh convergence.
    """
    from scipy.optimize import minimize
    from .neb_pathway import ClimbingImageMEPSolver,refine_path_saddle
    graph=percolation_thresholds(field)
    shape=np.array(np.shape(field));minimum_index=np.unravel_index(np.argmin(field),shape)
    start=lattice.get_cartesian_coords(np.array(minimum_index)/shape)
    def objective(x):
        e,f=evaluator([x]);return float(e[0]),-f[0]
    local_min=minimize(objective,start,jac=True,method='L-BFGS-B',options={'maxiter':100,'ftol':1e-12,'gtol':1e-7})
    energy_min=float(local_min.fun);bands=[]
    for witness in graph['percolating_cycles']['3D']:
        points=lattice.get_cartesian_coords(witness['fractional_path'])
        translation=points[-1]-points[0]
        index=int(np.argmin(evaluator(points[:-1])[0]))
        rotated=np.vstack((points[index:-1],points[:index+1]+translation))
        minimum=minimize(objective,rotated[0],jac=True,method='L-BFGS-B',options={'maxiter':100,'gtol':1e-7})
        rotated[0]=minimum.x;rotated[-1]=minimum.x+translation
        result=ClimbingImageMEPSolver().solve(rotated[0],rotated[-1],evaluator,images=25,initial_path=rotated,
                                             optimizer='fire',max_step_A=.05,step_size=.01,force_tolerance=.03,max_steps=max_steps)
        refined=refine_path_saddle(result['positions_A'],evaluator)
        result['refined_peak_energy_eV']=refined['peak_energy_eV'];bands.append(result)
    return {'raw_grid_barrier_3d_ev':graph['barriers_eV']['3D'],
            'refined_channel_barrier_3d_ev':max(b['refined_peak_energy_eV'] for b in bands)-energy_min,
            'converged':bool(local_min.success) and all(b['converged'] for b in bands),
            'minimum_energy_eV':energy_min,'bands':bands,'grid_shape':shape.tolist(),
            'qualification':'ABSTAIN'}


def percolation_thresholds(field, *, lattice=None, host_fractional=None, host_radii_A=None, neighborhood=26):
    """26-neighbor periodic union-find with integer image potentials and cycle rank.

    Each rank must occur within ONE connected component. Thresholds reference
    the global minimum; disconnected local cages do not imply a low barrier.
    """
    if neighborhood not in (6, 18, 26): raise ValueError('neighborhood must be 6, 18 or 26')
    values=np.asarray(field,float)
    if values.ndim!=3 or min(values.shape)<2 or values.size>262144 or not np.isfinite(values).all():
        raise ValueError('finite 3D field of at most 64^3 voxels required')
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
    neighbors=[np.array(v) for v in product((-1,0,1),repeat=3) if v!=(0,0,0) and sum(abs(x) for x in v) <= {6:1,18:2,26:3}[neighborhood]]
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
            'graph_neighborhood':neighborhood,'calibration_status':'UNQUALIFIED','qualification':'ABSTAIN'}


def build_softbv_evaluator(structure, *, screening_factor=.75):
    """A3 host Hamiltonian: native Morse wall and screened host-cation Coulomb.

    No additional anion Born-Mayer wall, unscreened contact switch, or fitted
    defect offset is included. This is an unqualified static model, not a
    many-body defect-formation calculation. Earlier constructors stay intact.
    """
    from .bvse_parameters import ANIONS,CATIONS
    if not np.isfinite(screening_factor) or screening_factor<=0:
        raise ValueError('positive finite cation screening required')
    cations=dict(CATIONS,Co=(3,.545))
    return SiteEnergyEvaluator(structure,
        anions={s:(v[1],v[2],v[0]) for s,v in ANIONS.items()},
        cations={s:(q,screening_factor*(.76+r),r) for s,(q,r) in cations.items() if s!='Li'},
        pauli=False,periodic_cutoff_A=8.)


class ValenceSumSiteEnergyEvaluator(SiteEnergyEvaluator):
    """Owner-proposed global valence-sum potential, not a validated BVSE model.

    Its 1/4 scaling is a hypothesis about the existing Morse minima. The
    weighted-depth expression is W*(S-2), W=sum(D_i*s_i), avoiding division
    at S=0. Anion bond valences have a C2 cutoff from 5 to 6 Angstrom.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.periodic_cutoff_A is None or self.periodic_cutoff_A < 6:
            raise ValueError('periodic cutoff of at least 6 A required')
        if not any(kind == 'morse' for kind, _, _ in self.parameter_groups):
            raise ValueError('at least one parameterized anion required')

    def _pair(self, kind, params, d, symbol):
        if kind == 'morse':
            return np.zeros_like(d), np.zeros_like(d)
        return super()._pair(kind, params, d, symbol)

    def __call__(self, positions):
        from scipy.spatial import cKDTree
        x=np.asarray(positions,float)
        energy,force=super().__call__(x)
        wrapped=self.lattice.get_cartesian_coords(self.lattice.get_fractional_coords(x)%1)
        pairs=self.image_tree.sparse_distance_matrix(cKDTree(wrapped),6.,output_type='coo_matrix')
        group=self.site_group_indices[self.image_site_indices[pairs.row]]
        count=len(x);total=np.zeros(count);weighted=np.zeros(count);records=[]
        for j,(kind,params,symbol) in enumerate(self.parameter_groups):
            if kind!='morse':continue
            mask=group==j;ix=pairs.col[mask];rows=pairs.row[mask];d=np.maximum(pairs.data[mask],1e-6)
            r0,b,depth=params;raw=.25*np.exp(np.clip((r0-d)/b,-100,100))
            u=np.clip(d-5.,0,1);switch=1-10*u**3+15*u**4-6*u**5
            dswitch=-30*u*u*(1-u)**2
            valence=raw*switch;derivative=raw*(dswitch-switch/b)
            np.add.at(total,ix,valence);np.add.at(weighted,ix,depth*valence)
            records.append((ix,rows,d,depth,valence,derivative))
        energy+=weighted*(total-2.)
        for ix,rows,d,depth,valence,derivative in records:
            excess=np.maximum(valence-.5,0.)
            np.add.at(energy,ix,depth*excess**2)
            slope=(depth*(total[ix]-2.)+weighted[ix]+2*depth*excess)*derivative
            np.add.at(force,ix,slope[:,None]*(self.image_positions[rows]-wrapped[ix])/d[:,None])
        return energy,force
