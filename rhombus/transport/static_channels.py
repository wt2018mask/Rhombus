"""Occupied-site periodic connectivity diagnostic, not a migration barrier model.

Empty interstitial paths and defects are absent. A negative graph is not proof
of an insulator and cannot falsify a candidate or authorize scientific compute.
"""
from itertools import product
import numpy as np


class StaticChannelScreener:
    def analyze(self, structure, *, mobile_species='Li', cutoff_angstrom=4., anion_radii=None):
        if not np.isfinite(cutoff_angstrom) or cutoff_angstrom<=0:
            raise ValueError('positive finite cutoff required')
        if not structure.is_ordered:
            return {'verdict':'DISORDERED_REQUIRES_ORDERING','qualification':'ABSTAIN','execution_authorized':False}
        ids=[i for i,s in enumerate(structure) if s.specie.symbol==mobile_species]
        if not ids:
            return {'verdict':'INDETERMINATE_NO_MOBILE_SITES','qualification':'ABSTAIN','execution_authorized':False}
        lattice=structure.lattice.matrix
        bound=int(np.ceil(cutoff_angstrom/np.linalg.svd(lattice,compute_uv=False).min()))+1
        if bound>4: raise ValueError('periodic image budget exceeded')
        radii={} if anion_radii is None else anion_radii
        if any(not np.isfinite(v) or v<=0 for v in radii.values()):raise ValueError('positive radii required')
        edges=[[] for _ in ids]; apertures=[]
        for a,i in enumerate(ids):
            for b,j in enumerate(ids):
                for image in product(range(-bound,bound+1),repeat=3):
                    shift=np.array(image); delta=structure[j].frac_coords+shift-structure[i].frac_coords
                    distance=np.linalg.norm(delta@lattice)
                    if distance<1e-10 or distance>cutoff_angstrom:continue
                    edges[a].append((b,shift))
                    if radii:
                        samples=structure[i].frac_coords+np.linspace(0,1,17)[:,None]*delta
                        values=[]
                        for site in structure:
                            if site.specie.symbol in radii:
                                distances=structure.lattice.get_all_distances(samples,[site.frac_coords])[:,0]
                                values.append(distances.min()-radii[site.specie.symbol])
                        if values:apertures.append(float(min(values)))
        rank=0
        visited={}
        for start in range(len(ids)):
            if start in visited:continue
            visited[start]=np.zeros(3,dtype=int); queue=[start]; cycles=[]
            while queue:
                a=queue.pop()
                for b,shift in edges[a]:
                    target=visited[a]+shift
                    if b not in visited:visited[b]=target;queue.append(b)
                    else:cycles.append(target-visited[b])
            if cycles:rank=max(rank,int(np.linalg.matrix_rank(np.array(cycles,dtype=float))))
        return {'schema_version':'rhombus-static-channel-diagnostic-v1',
                'verdict':f'PERCOLATING_{rank}D' if rank else 'NON_PERCOLATING_ISOLATED_CAGE',
                'occupied_site_periodic_rank':rank,'sampled_edge_clearance_min_A':min(apertures) if apertures else None,
                'barrier_proxy_eV':None,'barrier_status':'NO_CALIBRATED_ELECTROSTATIC_OR_BOND_VALENCE_MODEL',
                'limitations':['Occupied sites only; defects/interstitials missing','Sampled clearance is not a validated migration bottleneck'],
                'qualification':'ABSTAIN','execution_authorized':False,'candidate_falsified':False}
