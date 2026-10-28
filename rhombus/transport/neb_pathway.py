"""Bounded climbing-image elastic band with a caller-supplied evaluator."""
from typing import Protocol
import heapq
from itertools import product
import numpy as np


def relax_endpoint_local_basin(position,evaluator,*,radius_A=.45,force_tolerance=1e-3,max_steps=300,max_step_A=.05):
    """Projected 3D BFGS with Armijo search and a spherical basin constraint.

    A constrained boundary minimum with a nonzero physical gradient is reported
    NONSTATIONARY, never mistaken for an unconstrained stationary endpoint.
    """
    origin=np.asarray(position,float);x=origin.copy();inverse=np.eye(3)
    if (origin.shape!=(3,) or not np.isfinite(origin).all() or not 0<radius_A<=1 or not 0<force_tolerance<=.1
        or not 1<=max_steps<=1000 or not 0<max_step_A<=.1):
        raise ValueError('finite endpoint and bounded basin required')
    def evaluate(p):
        e,f=map(np.asarray,evaluator([p]))
        if e.shape!=(1,) or f.shape!=(1,3) or not np.isfinite(e).all() or not np.isfinite(f).all():
            raise ValueError('invalid endpoint evaluator')
        return float(e[0]),-f[0]
    energy,gradient=evaluate(x);steps=0
    for steps in range(max_steps):
        if np.linalg.norm(gradient)<=force_tolerance:break
        direction=-inverse@gradient
        if gradient@direction>=0:inverse=np.eye(3);direction=-gradient
        direction*=min(1,max_step_A/max(np.linalg.norm(direction),1e-30))
        accepted=False;scale=1.
        for _ in range(30):
            trial=x+scale*direction;delta=trial-origin
            if np.linalg.norm(delta)>radius_A:trial=origin+radius_A*delta/np.linalg.norm(delta)
            move=trial-x
            if np.linalg.norm(move)<1e-12:break
            new_energy,new_gradient=evaluate(trial)
            if new_energy<=energy+1e-4*float(gradient@move):accepted=True;break
            scale*=.5
        if not accepted:break
        change=new_gradient-gradient;curvature=float(change@move)
        if curvature>1e-12:
            rho=1/curvature;a=np.eye(3)-rho*np.outer(move,change)
            inverse=a@inverse@a.T+rho*np.outer(move,move)
        else:inverse=np.eye(3)
        x,energy,gradient=trial,new_energy,new_gradient
    norm=float(np.linalg.norm(gradient));distance=float(np.linalg.norm(x-origin))
    return {'position_A':x.tolist(),'nominal_position_A':origin.tolist(),'energy_eV':energy,
            'force_norm_eV_A':norm,'stationary':norm<=force_tolerance,'displacement_A':distance,
            'basin_radius_A':radius_A,'iterations':steps+1,
            'status':'STATIONARY' if norm<=force_tolerance else 'BASIN_BOUNDARY_NONSTATIONARY' if distance>=radius_A-1e-6 else 'OPTIMIZATION_NOT_CONVERGED'}


def initialize_relaxed_pathway(field,lattice,initial,final,evaluator,*,images=17,basin_radius_A=.45):
    endpoints=[relax_endpoint_local_basin(p,evaluator,radius_A=basin_radius_A) for p in (initial,final)]
    if np.linalg.norm(np.array(endpoints[0]['position_A'])-endpoints[1]['position_A'])<.1:
        raise ValueError('endpoint basins collapsed to the same site')
    path=initialize_pathway_from_voxel_grid(field,lattice,*[e['position_A'] for e in endpoints],images=images)
    path['endpoint_relaxations']=endpoints;path['endpoint_stationary']=all(e['stationary'] for e in endpoints)
    return path


def resample_pathway(points, images):
    points=np.asarray(points,float)
    if points.ndim!=2 or points.shape[1]!=3 or len(points)<2 or not np.isfinite(points).all():
        raise ValueError('finite Cartesian path required')
    distances=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
    keep=np.r_[True,np.diff(distances)>1e-12]
    if distances[-1]<=1e-10:raise ValueError('zero length path')
    return np.column_stack([np.interp(np.linspace(0,distances[-1],images),distances[keep],points[keep,k]) for k in range(3)])


def refine_path_saddle(points, evaluator):
    """Bounded golden-section maxima on each continuous polyline segment.

    This refines sampling on the supplied path, not a transverse optimization
    or proof of the globally lowest migration pathway.
    """
    from scipy.optimize import minimize_scalar
    path=np.asarray(points,float)
    if path.ndim!=2 or path.shape[1]!=3 or not np.isfinite(path).all() or len(path)<2:
        raise ValueError('finite polyline required')
    energy=np.asarray(evaluator(path)[0]);best=int(np.argmax(energy))
    maximum=float(energy[best]);position=path[best]
    for a,b in zip(path[:-1],path[1:]):
        if np.linalg.norm(b-a)<1e-12:continue
        result=minimize_scalar(lambda t:-float(evaluator([a+t*(b-a)])[0][0]),bounds=(0,1),method='bounded',options={'xatol':1e-6})
        if -result.fun>maximum:maximum=float(-result.fun);position=a+result.x*(b-a)
    return {'peak_energy_eV':maximum,'position_A':position.tolist(),'barrier_ev':maximum-float(energy[0]),
            'scope':'SEGMENT_SADDLE_REFINEMENT_NOT_GLOBAL_MEP_PROOF'}


def initialize_pathway_from_voxel_grid(field, lattice, initial, final, *, images=15, beta=1., max_visited=250000):
    """Two exact graph passes: minimax threshold, then integral at that threshold.

    A single lexicographic label is insufficient: prefix maxima may later tie.
    Search the bounded unwrapped covering graph so endpoint winding is preserved.
    This is a grid initializer, not a continuum saddle or convergence proof.
    """
    values=np.asarray(field,float); shape=np.array(values.shape)
    if (values.ndim!=3 or min(shape)<2 or values.size>262144 or not np.isfinite(values).all()
        or not np.isfinite(beta) or beta<=0 or not 3<=images<=64):
        raise ValueError('bounded finite grid and path configuration required')
    endpoints=np.asarray([initial,final],float)
    if endpoints.shape!=(2,3) or not np.isfinite(endpoints).all():raise ValueError('finite endpoints required')
    start,end=[tuple(v) for v in np.rint(lattice.get_fractional_coords(endpoints)*shape).astype(int)]
    if start==end:raise ValueError('hop shorter than grid resolution')
    lower=np.minimum(start,end)-shape//2;upper=np.maximum(start,end)+shape//2
    steps=[np.array(v) for v in product((-1,0,1),repeat=3) if v!=(0,0,0)]
    lengths=[np.linalg.norm(lattice.get_cartesian_coords(v/shape)) for v in steps]
    energy=lambda node:float(values[tuple(np.array(node)%shape)])
    minimum=float(values.min())
    def search(threshold=None):
        initial_cost=energy(start) if threshold is None else 0.
        best={start:initial_cost};previous={};queue=[(initial_cost,start)];visited=0
        while queue:
            cost,node=heapq.heappop(queue)
            if cost!=best[node]:continue
            visited+=1
            if visited>max_visited:raise ValueError('voxel pathway search budget exhausted')
            if node==end:
                path=[node]
                while path[-1]!=start:path.append(previous[path[-1]])
                return cost,path[::-1]
            pos=np.array(node)
            for step,length in zip(steps,lengths):
                raw=pos+step
                if np.any(raw<lower) or np.any(raw>upper):continue
                other=tuple(raw);v=energy(other)
                if threshold is not None and v>threshold+1e-10:continue
                proposal=(max(cost,v) if threshold is None else
                          cost+length*np.exp(np.clip(beta*(v-minimum),-600,600)))
                if proposal<best.get(other,float('inf')):
                    best[other]=proposal;previous[other]=node;heapq.heappush(queue,(proposal,other))
        raise ValueError('no bounded voxel pathway')
    peak,_=search()
    integral,nodes=search(peak)
    points=lattice.get_cartesian_coords(np.array(nodes)/shape)
    points=np.vstack((endpoints[0],points,endpoints[1]))
    sampled=resample_pathway(points,images)
    return {'positions_A':points.tolist(),'images_A':sampled.tolist(),'minimax_peak_energy_eV':peak,
            'secondary_integral_shifted':float(integral),'grid_shape':shape.tolist(),
            'scope':'BOUNDED_UNWRAPPED_VOXEL_GRAPH_NOT_CONTINUUM_OPTIMUM'}

class EnergyForceEvaluator(Protocol):
    def __call__(self, positions): ...


class ClimbingImageMEPSolver:
    def solve(self, initial, final, evaluator: EnergyForceEvaluator, *, images=7, max_steps=200,
              force_tolerance=.01, step_size=.02, spring=1., host_positions=None, steric_A=.5,
              initial_path=None, optimizer='gradient', max_step_A=.1):
        start,end=np.asarray(initial,float),np.asarray(final,float)
        if (start.shape!=(3,) or end.shape!=(3,) or not np.isfinite([start,end]).all()
            or np.linalg.norm(end-start)<1e-10 or not 3<=images<=64 or not 1<=max_steps<=2000
            or optimizer not in ('gradient','fire')
            or not all(np.isfinite(v) and v>0 for v in (force_tolerance,step_size,spring,steric_A,max_step_A))):
            raise ValueError('invalid bounded path configuration')
        chain=np.linspace(start,end,images) if initial_path is None else resample_pathway(initial_path,images)
        chain[0],chain[-1]=start,end
        host=None if host_positions is None else np.asarray(host_positions,float)
        if host is not None and (host.ndim!=2 or host.shape[1]!=3 or not np.isfinite(host).all()):raise ValueError('invalid host')
        def avoid_collisions():
            if host is None:return
            for i in range(1,images-1):
                for _ in range(20):
                    delta=chain[i]-host; distances=np.linalg.norm(delta,axis=1)
                    if not len(distances) or distances.min()>=steric_A:break
                    j=int(distances.argmin()); direction=delta[j]
                    if np.linalg.norm(direction)<1e-10:
                        tangent=end-start; direction=np.cross(tangent,[1.,0,0])
                        if np.linalg.norm(direction)<1e-10:direction=np.cross(tangent,[0.,1,0])
                    chain[i]+=direction/np.linalg.norm(direction)*(steric_A-distances[j]+1e-6)
        avoid_collisions();converged=False; residual=float('inf')
        velocity=np.zeros_like(chain);dt=step_size;alpha=.1;positive=0
        perpendicular_residual=float('inf')
        for iteration in range(max_steps):
            energy,forces=map(np.asarray,evaluator(chain))
            if energy.shape!=(images,) or forces.shape!=chain.shape or not np.isfinite(energy).all() or not np.isfinite(forces).all():raise ValueError('invalid evaluator output')
            peak=int(np.argmax(energy[1:-1]))+1; effective=np.zeros_like(chain);perpendicular_residual=0.
            for i in range(1,images-1):
                if optimizer=='gradient':tangent=chain[i+1]-chain[i-1]
                elif energy[i+1]>energy[i]>energy[i-1]:tangent=chain[i+1]-chain[i]
                elif energy[i+1]<energy[i]<energy[i-1]:tangent=chain[i]-chain[i-1]
                else:
                    diff=np.abs(energy[i-1:i+2:2]-energy[i]);high,low=max(diff),min(diff)
                    tangent=((chain[i+1]-chain[i])*high+(chain[i]-chain[i-1])*low if energy[i+1]>energy[i-1]
                             else (chain[i+1]-chain[i])*low+(chain[i]-chain[i-1])*high)
                    if np.linalg.norm(tangent)<1e-12:tangent=chain[i+1]-chain[i-1]
                length=np.linalg.norm(tangent)
                if length<1e-12:raise ValueError('degenerate path tangent')
                tangent/=length; parallel=np.dot(forces[i],tangent)*tangent
                perpendicular_residual=max(perpendicular_residual,float(np.linalg.norm(forces[i]-parallel)))
                effective[i]=forces[i]-parallel+spring*(np.linalg.norm(chain[i+1]-chain[i])-np.linalg.norm(chain[i]-chain[i-1]))*tangent
                if i==peak:effective[i]=forces[i]-2*parallel
            residual=float(np.linalg.norm(effective[1:-1],axis=1).max())
            if residual<=force_tolerance:converged=True;break
            if iteration==max_steps-1:break
            if optimizer=='fire':
                velocity+=dt*effective
                power=float(np.sum(velocity*effective))
                if power>0:
                    positive+=1
                    norm=np.linalg.norm(effective)
                    if norm>0:velocity=(1-alpha)*velocity+alpha*np.linalg.norm(velocity)*effective/norm
                    if positive>5:dt=min(dt*1.1,.1);alpha*=.99
                else:
                    velocity[:]=0;dt*=.5;alpha=.1;positive=0
                update=dt*velocity[1:-1]
            else:update=step_size*effective[1:-1]
            lengths=np.linalg.norm(update,axis=1)
            chain[1:-1]+=update/np.maximum(1,lengths[:,None]/max_step_A);avoid_collisions()
        perpendicular=[]
        for i in range(1,images-1):
            tangent=chain[i+1]-chain[i-1];tangent/=np.linalg.norm(tangent)
            perpendicular.append(np.linalg.norm(forces[i]-np.dot(forces[i],tangent)*tangent))
        clearance=float(np.linalg.norm(chain[:,None,:]-host[None,:,:],axis=2).min()) if host is not None and len(host) else None
        if clearance is not None and clearance<steric_A:converged=False
        return {'schema_version':'rhombus-climbing-band-v1','barrier_ev':float(max(energy)-energy[0]),
                'reverse_barrier_ev':float(max(energy)-energy[-1]),'max_band_force_ev_per_angstrom':residual,
                'max_perp_force_ev_per_angstrom':perpendicular_residual,
                'min_host_clearance_angstrom':clearance,'converged':converged,'iterations':iteration+1,
                'positions_A':chain.tolist(),'energies_eV':energy.tolist(),
                'endpoint_max_force_ev_per_angstrom':float(np.linalg.norm(forces[[0,-1]],axis=1).max()),
                'endpoints_stationary':bool(np.linalg.norm(forces[[0,-1]],axis=1).max()<=force_tolerance),
                'optimizer':optimizer,'initialization':'CURVED_INPUT' if initial_path is not None else 'LINEAR',
                'maximum_step_A':max_step_A,
                'gate_verdict':'UNQUALIFIED_BARRIER' if converged else 'UNCONVERGED_INDETERMINATE',
                'qualification':'ABSTAIN'}


class ASEMobileIonEvaluator:
    """Optional fixed-host ASE calculator adapter; never loads a model itself.

    Host code must explicitly permit evaluation. A calculator may be MACE or
    another ASE implementation; independence/applicability remain unverified.
    """
    def __init__(self, atoms, mobile_index, calculator, *, allow_evaluation=False):
        if type(mobile_index) is not int or not 0<=mobile_index<len(atoms):raise ValueError('invalid mobile atom index')
        self.atoms=atoms.copy();self.index=mobile_index;self.calculator=calculator
        self.allowed=allow_evaluation is True

    def __call__(self, positions):
        if not self.allowed:raise PermissionError('explicit host permission for force evaluation required')
        points=np.asarray(positions,float)
        if points.ndim!=2 or points.shape[1]!=3 or not np.isfinite(points).all():raise ValueError('finite path points required')
        energies=[];forces=[]
        for point in points:
            atoms=self.atoms.copy();atoms.positions[self.index]=point;atoms.calc=self.calculator
            energies.append(float(atoms.get_potential_energy()));forces.append(atoms.get_forces()[self.index])
        return np.array(energies),np.array(forces)
