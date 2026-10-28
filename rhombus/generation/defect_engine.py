"""Bounded formal-charge defect enumeration with explicit Ewald assumptions."""
from itertools import combinations, product
import math
import numpy as np
from pymatgen.analysis.ewald import EwaldSummation
from pymatgen.core import Species
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer


def expand_supercell(structure, *, minimum_length_A=9.5, max_atoms=512):
    if not math.isfinite(minimum_length_A) or minimum_length_A <= 0 or not 1 <= max_atoms <= 1024:
        raise ValueError('invalid supercell budget')
    # Plane spacings also protect against short images in skew cells.
    heights = 1 / np.linalg.norm(structure.lattice.reciprocal_lattice_crystallographic.matrix, axis=1)
    multiples = np.maximum(1, np.ceil(minimum_length_A / heights).astype(int))
    if len(structure) * np.prod(multiples) > max_atoms:
        raise ValueError('supercell atom budget exceeded')
    result = structure.copy()
    # Structure.from_dict may carry an explicit old charge=0. Reset it so
    # removing/substituting sites cannot retain the parent's stale charge.
    result.unset_charge()
    result.make_supercell(multiples)
    return result


def decorate_charges(structure, charges=None):
    from rhombus.transport.bvse_parameters import oxidation_states
    if not structure.is_ordered:
        raise ValueError('order fractional occupancies first')
    result = structure.copy()
    result.unset_charge()
    mapping = oxidation_states() if charges is None else charges
    for i, site in enumerate(result):
        charge = getattr(site.specie, 'oxi_state', None)
        if charge is None:
            if site.specie.symbol not in mapping:
                raise ValueError('explicit oxidation state required: ' + site.specie.symbol)
            charge = mapping[site.specie.symbol]
        if not math.isfinite(charge):
            raise ValueError('finite formal charges required')
        result.replace(i, Species(site.specie.symbol, charge))
    return result


def _ewald(structure):
    return float(EwaldSummation(structure, acc_factor=6).total_energy)


def _receipt(structure, vacancies, interstitials, *, mode, parent_li_count, energy, parent):
    li_count = sum(s.specie.symbol == 'Li' for s in structure)
    return {'mode': mode, 'structure': structure.as_dict(),
            'carrier_vacancy_fraction': len(vacancies) / max(1, parent_li_count),
            'vacant_fractional_targets': [list(map(float, p)) for p in vacancies],
            'interstitial_fractional_sites': [list(map(float, p)) for p in interstitials],
            'parent_mobile_fractional': [s.frac_coords.tolist() for s in parent if s.specie.symbol == 'Li'],
            'mobile_count': li_count, 'formal_charge_e': float(structure.charge),
            'ewald_energy_eV': energy, 'ewald_scope': 'FORMAL_CHARGES_PERIODIC_BACKGROUND_NO_DEFECT_FORMATION_ENERGY',
            'charge_compensated': abs(structure.charge) < 1e-8,
            'qualification': 'ABSTAIN'}


def seed_vacancies(structure, *, minimum_length_A=9.5, top_k=1, max_configurations=32, charges=None):
    """Enumerate symmetry-distinct single-Li vacancies; charged probes are labeled.

    A Li vacancy alone is not charge neutral. Ewald uses the periodic charged-cell
    background convention; the ranking does not prove physical defect stability.
    """
    if not 1 <= top_k <= max_configurations <= 128:
        raise ValueError('invalid enumeration budget')
    host = decorate_charges(expand_supercell(structure, minimum_length_A=minimum_length_A), charges)
    groups = SpacegroupAnalyzer(host, symprec=1e-3).get_symmetrized_structure().equivalent_indices
    representatives = [group[0] for group in groups if host[group[0]].specie.symbol == 'Li']
    if not representatives:
        raise ValueError('no mobile Li sites')
    if len(representatives) > max_configurations:
        raise ValueError('symmetry-distinct defect budget exceeded')
    count = sum(s.specie.symbol == 'Li' for s in host)
    result = []
    for index in representatives:
        child = host.copy()
        target = child[index].frac_coords.copy()
        child.remove_sites([index])
        result.append(_receipt(child, [target], [], mode='INTRINSIC_VACANCY_PROBE',
                               parent_li_count=count, energy=_ewald(child), parent=host))
    return sorted(result, key=lambda row: (row['ewald_energy_eV'], row['vacant_fractional_targets']))[:top_k]


def substitute_aliovalent(structure, *, site_index, dopant, dopant_charge,
                         interstitial_fractional=None, top_k=1, max_configurations=64, charges=None):
    """One substitution, integer Li compensation, Ewald-ranked bounded orderings.

    Call expand_supercell first so site_index has an unambiguous identity.
    Interstitial coordinates are explicit input, never silently invented.
    """
    if not 1 <= top_k <= max_configurations <= 128 or not math.isfinite(dopant_charge):
        raise ValueError('invalid substitution budget or charge')
    host = decorate_charges(structure, charges)
    if not 0 <= site_index < len(host) or host[site_index].specie.symbol == 'Li':
        raise ValueError('framework substitution index required')
    if abs(host.charge) > 1e-8:
        raise ValueError('neutral parent required for compensated substitution')
    host.replace(site_index, Species(dopant, dopant_charge))
    delta = float(host.charge)
    if abs(delta - round(delta)) > 1e-8 or abs(delta) > 3:
        raise ValueError('bounded integral Li compensation required')
    n = round(delta)
    mobile = [i for i, s in enumerate(host) if s.specie.symbol == 'Li']
    parent_mobile_count = len(mobile)
    if n > 0:
        if math.comb(len(mobile), n) > max_configurations:
            # Explicitly bounded nearest-to-dopant subset, not exhaustive ordering.
            mobile = sorted(mobile, key=lambda i: (host.get_distance(i, site_index), i))
            while len(mobile) > n and math.comb(len(mobile), n) > max_configurations:
                mobile.pop()
        removals = list(combinations(mobile, n))
        if not removals:
            raise ValueError('insufficient Li compensation sites')
        result = []
        for indices in removals:
            child = host.copy()
            targets = [child[i].frac_coords.copy() for i in indices]
            child.remove_sites(indices)
            result.append(_receipt(child, targets, [], mode='ALIOVALENT_SUBSTITUTION',
                                   parent_li_count=parent_mobile_count, energy=_ewald(child), parent=host))
    elif n < 0:
        points = np.asarray(interstitial_fractional, float)
        if points.shape != (-n, 3) or not np.isfinite(points).all():
            raise ValueError('explicit finite compensation interstitial coordinates required')
        child = host.copy()
        for point in points:
            if child.lattice.get_all_distances([point], child.frac_coords).min() < 1.:
                raise ValueError('interstitial collision')
            child.append(Species('Li', 1), point)
        result = [_receipt(child, [], points, mode='ALIOVALENT_SUBSTITUTION',
                           parent_li_count=len(mobile), energy=_ewald(child), parent=host)]
    else:
        raise ValueError('isovalent substitution creates no carrier defects')
    for row in result:
        row['ordering_scope'] = 'BOUNDED_ENUMERATION_NOT_EXHAUSTIVE_GLOBAL_MINIMUM'
        if not row['charge_compensated']:
            raise ValueError('charge compensation failed')
    return sorted(result, key=lambda row: row['ewald_energy_eV'])[:top_k]


def order_fractional(structure, *, top_k=1, max_configurations=128):
    """Exact finite enumeration at fixed composition on the supplied cell.

    Expand to integer species counts before calling. Fractional populations not
    representable in this cell are rejected, not rounded to another chemistry.
    """
    if not 1 <= top_k <= max_configurations <= 128 or len(structure) > 512:
        raise ValueError('invalid ordering budget')
    choices = [tuple(site.species.items()) + ((None, 1-sum(site.species.values())),)
               if sum(site.species.values()) < 1-1e-8 else tuple(site.species.items()) for site in structure]
    count = math.prod(len(c) for c in choices)
    if count > max_configurations:
        if all(len(site.species)==1 and (site.is_ordered or next(iter(site.species)).symbol=='Li') for site in structure):
            if top_k!=1:raise ValueError('bounded mobile-site optimizer returns one ordering')
            return [order_mobile_sites(structure)]
        raise ValueError('fractional ordering budget exceeded')
    target = structure.composition
    if any(abs(v - round(v)) > 1e-8 for v in target.values()):
        raise ValueError('supercell with integral species populations required')
    from pymatgen.core import Structure
    output = []
    for selection in product(*choices):
        occupied = [i for i, v in enumerate(selection) if v[0] is not None]
        child = Structure(structure.lattice, [selection[i][0] for i in occupied], structure.frac_coords[occupied])
        if child.composition != target:
            continue
        child = decorate_charges(child)
        if abs(child.charge) > 1e-8:
            continue
        li=[i for i,s in enumerate(child) if s.specie.symbol=='Li']
        if len(li)>1:
            distances=child.distance_matrix[np.ix_(li,li)]+np.eye(len(li))*1e6
            if distances.min()<1.95-1e-8:continue
        output.append({'structure': child.as_dict(), 'ewald_energy_eV': _ewald(child),
                       'qualification': 'ABSTAIN'})
    if not output:
        raise ValueError('no charge-balanced ordering within supplied cell')
    return sorted(output, key=lambda row: row['ewald_energy_eV'])[:top_k]


def mobile_site_capacity(lattice, fractional_sites, *, minimum_distance_A=1.95,
                         split_distance_A=1.25, time_limit_seconds=10.):
    """Certify the geometric maximum independent set or fail explicitly.

    Split clusters are audited, not collapsed transitively: a connected chain
    of overlapping sites need not be a clique. Capacity is conditional on the
    supplied site universe and distance rule, not a universal carrier density.
    """
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_matrix
    sites=np.asarray(fractional_sites,float)
    if (sites.ndim!=2 or sites.shape[1]!=3 or not 1<=len(sites)<=256 or not np.isfinite(sites).all()
        or not 0<split_distance_A<=minimum_distance_A or not 0<time_limit_seconds<=30):
        raise ValueError('bounded finite mobile-site graph required')
    distances=lattice.get_all_distances(sites,sites)
    edges=np.array([(i,j) for i in range(len(sites)) for j in range(i) if distances[i,j]<minimum_distance_A-1e-8],int).reshape(-1,2)
    parent=list(range(len(sites)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,j in edges:
        if distances[i,j]<split_distance_A:parent[find(int(i))]=find(int(j))
    clusters={}
    for i in range(len(sites)):clusters.setdefault(find(i),[]).append(i)
    rows=np.repeat(np.arange(len(edges)),2);cols=edges.ravel()
    matrix=coo_matrix((np.ones(len(cols)),(rows,cols)),shape=(len(edges),len(sites))).tocsr()
    constraints=LinearConstraint(matrix,-np.inf,np.ones(len(edges)))
    result=milp(-np.ones(len(sites)),integrality=np.ones(len(sites)),bounds=Bounds(0,1),
                constraints=constraints,options={'time_limit':time_limit_seconds,'mip_rel_gap':0.})
    if not result.success:raise ValueError('maximum non-overlapping capacity not certified within budget')
    maximum=int(round(-result.fun))
    return {'maximum_occupiable_sites':maximum,'capacity_certified':True,
            'capacity_scope':'MAXIMUM_INDEPENDENT_SET_OF_SUPPLIED_PERIODIC_SITE_GRAPH',
            'minimum_distance_A':minimum_distance_A,'split_clusters':list(clusters.values()),
            'edges':edges,'constraint_matrix':matrix,'distances':distances,'witness':np.flatnonzero(result.x>.5)}


def order_mobile_sites(structure, *, mobile_count=None, minimum_distance_A=1.95,
                       split_distance_A=1.25, swap_attempts=1000, seed=0):
    """Feasible fixed-population MILP seed + exact Ewald-matrix 1/2 swaps."""
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import vstack,csr_matrix
    from pymatgen.core import Structure
    if len(structure)>512 or not 0<=swap_attempts<=5000:raise ValueError('ordering resource budget')
    host=[];mobile=[]
    for site in structure:
        symbols={sp.symbol for sp in site.species}
        if symbols=={'Li'}:mobile.append(site.frac_coords)
        elif site.is_ordered:host.append(site)
        else:raise ValueError('order framework substitution/disorder explicitly first')
    nominal=float(structure.composition.element_composition['Li'])
    number=round(nominal) if mobile_count is None else mobile_count
    if type(number) is not int or number<1 or (mobile_count is None and abs(nominal-number)>1e-6):
        raise ValueError('explicit integer mobile population required; no silent occupancy rounding')
    capacity=mobile_site_capacity(structure.lattice,mobile,minimum_distance_A=minimum_distance_A,split_distance_A=split_distance_A)
    maximum=capacity['maximum_occupiable_sites']
    if number>maximum:raise ValueError(f'Pauli site capacity {maximum} below required Li population {number}')
    full=decorate_charges(Structure(structure.lattice,[s.specie for s in host]+[Species('Li',1)]*len(mobile),
                                    [s.frac_coords for s in host]+mobile))
    energy=EwaldSummation(full,acc_factor=6).total_energy_matrix;h=len(host);n=len(mobile)
    linear=np.array([2*energy[h+i,:h].sum()+energy[h+i,h+i] for i in range(n)])
    matrix=vstack([capacity['constraint_matrix'],csr_matrix(np.ones((1,n)))])
    lower=np.r_[np.full(capacity['constraint_matrix'].shape[0],-np.inf),number]
    upper=np.r_[np.ones(capacity['constraint_matrix'].shape[0]),number]
    result=milp(linear+np.arange(n)*1e-9,integrality=np.ones(n),bounds=Bounds(0,1),
                constraints=LinearConstraint(matrix,lower,upper),options={'time_limit':10.,'mip_rel_gap':0.})
    if result.x is None:raise ValueError('no feasible Pauli ordering within budget')
    selected=sorted(np.flatnonzero(result.x>.5).tolist())
    def score(indices):
        ids=np.r_[np.arange(h),h+np.array(indices)];return float(energy[np.ix_(ids,ids)].sum())
    def feasible(indices):
        d=capacity['distances'][np.ix_(indices,indices)]+np.eye(len(indices))*1e6
        return d.min()>=minimum_distance_A-1e-8
    if len(selected)!=number or not feasible(selected):raise ValueError('invalid integer ordering witness')
    rng=np.random.default_rng(seed);best=score(selected)
    for attempt in range(swap_attempts):
        unused=sorted(set(range(n))-set(selected));k=2 if attempt%2 and min(len(unused),number)>=2 else 1
        if not unused:break
        remove=set(rng.choice(selected,k,replace=False));add=rng.choice(unused,k,replace=False).tolist()
        proposal=sorted([i for i in selected if i not in remove]+add)
        if feasible(proposal):
            value=score(proposal)
            if value<best-1e-9:selected,best=proposal,value
    ids=list(range(h))+[h+i for i in selected]
    child=Structure(full.lattice,[full[i].specie for i in ids],[full[i].frac_coords for i in ids])
    if abs(child.charge)>1e-8:raise ValueError('ordered structure not charge neutral')
    available=[i for i in range(n) if i not in selected]
    return {'structure':child.as_dict(),'ewald_energy_eV':_ewald(child),'parent_mobile_fractional':[list(map(float,p)) for p in mobile],
            'vacant_fractional_targets':[list(map(float,mobile[i])) for i in available],
            'maximum_occupiable_sites':maximum,'capacity_certified':True,
            'raw_crystallographic_site_count':n,'stoichiometric_vacancy_fraction':(maximum-number)/maximum,
            'carrier_vacancy_fraction':(maximum-number)/maximum,'minimum_li_li_distance_A':float((child.distance_matrix[np.ix_(range(h,len(child)),range(h,len(child)))]+np.eye(number)*1e6).min()),
            'split_clusters':capacity['split_clusters'],'source_li_population':nominal,
            'ordered_li_population':number,'seed':seed,'swap_attempts':swap_attempts,
            'ordering_scope':'CERTIFIED_GEOMETRIC_CAPACITY_LOCAL_EWALD_ORDERING_NOT_GLOBAL_ENERGY_MINIMUM',
            'qualification':'ABSTAIN'}
