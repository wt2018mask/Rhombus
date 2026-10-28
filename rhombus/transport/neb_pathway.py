"""Bounded climbing-image elastic band with a caller-supplied evaluator."""
from typing import Protocol
import numpy as np

class EnergyForceEvaluator(Protocol):
    def __call__(self, positions): ...


class ClimbingImageMEPSolver:
    def solve(self, initial, final, evaluator: EnergyForceEvaluator, *, images=7, max_steps=200,
              force_tolerance=.01, step_size=.02, spring=1., host_positions=None, steric_A=.5):
        start,end=np.asarray(initial,float),np.asarray(final,float)
        if (start.shape!=(3,) or end.shape!=(3,) or not np.isfinite([start,end]).all()
            or np.linalg.norm(end-start)<1e-10 or not 3<=images<=64 or not 1<=max_steps<=2000
            or not all(np.isfinite(v) and v>0 for v in (force_tolerance,step_size,spring,steric_A))):
            raise ValueError('invalid bounded path configuration')
        chain=np.linspace(start,end,images)
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
        for iteration in range(max_steps):
            energy,forces=map(np.asarray,evaluator(chain))
            if energy.shape!=(images,) or forces.shape!=chain.shape or not np.isfinite(energy).all() or not np.isfinite(forces).all():raise ValueError('invalid evaluator output')
            peak=int(np.argmax(energy[1:-1]))+1; effective=np.zeros_like(chain)
            for i in range(1,images-1):
                tangent=chain[i+1]-chain[i-1]; length=np.linalg.norm(tangent)
                if length<1e-12:raise ValueError('degenerate path tangent')
                tangent/=length; parallel=np.dot(forces[i],tangent)*tangent
                effective[i]=forces[i]-parallel+spring*(np.linalg.norm(chain[i+1]-chain[i])-np.linalg.norm(chain[i]-chain[i-1]))*tangent
                if i==peak:effective[i]=forces[i]-2*parallel
            residual=float(np.linalg.norm(effective[1:-1],axis=1).max())
            if residual<=force_tolerance:converged=True;break
            if iteration==max_steps-1:break
            update=step_size*effective[1:-1]; lengths=np.linalg.norm(update,axis=1)
            chain[1:-1]+=update/np.maximum(1,lengths[:,None]/.1);avoid_collisions()
        perpendicular=[]
        for i in range(1,images-1):
            tangent=chain[i+1]-chain[i-1];tangent/=np.linalg.norm(tangent)
            perpendicular.append(np.linalg.norm(forces[i]-np.dot(forces[i],tangent)*tangent))
        clearance=float(np.linalg.norm(chain[:,None,:]-host[None,:,:],axis=2).min()) if host is not None and len(host) else None
        if clearance is not None and clearance<steric_A:converged=False
        return {'schema_version':'rhombus-climbing-band-v1','barrier_ev':float(max(energy)-energy[0]),
                'reverse_barrier_ev':float(max(energy)-energy[-1]),'max_band_force_ev_per_angstrom':residual,
                'max_perp_force_ev_per_angstrom':float(max(perpendicular)),
                'min_host_clearance_angstrom':clearance,'converged':converged,'iterations':iteration+1,
                'positions_A':chain.tolist(),'energies_eV':energy.tolist(),
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
