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
        output.append({'structure': child.as_dict(), 'ewald_energy_eV': _ewald(child),
                       'qualification': 'ABSTAIN'})
    if not output:
        raise ValueError('no charge-balanced ordering within supplied cell')
    return sorted(output, key=lambda row: row['ewald_energy_eV'])[:top_k]
