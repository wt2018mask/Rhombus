"""Source-bound crystal inputs, explicit disorder probes and unavailable sources.

Randomized source CIFs and generated orderings are never labeled experimental
refinements. No target material conductivity or reserved TEST data is loaded.
"""
import hashlib
from pathlib import Path
import numpy as np
from pymatgen.core import Structure, Species
from pymatgen.analysis.ewald import EwaldSummation
from rhombus.generation.defect_engine import expand_supercell, seed_vacancies, substitute_aliovalent, decorate_charges

ARCHETYPES = ('gamma_LiAlO2','Li2S','Li2S_vacancy','Li2S_Cl_vacancy','tetragonal_LLZO',
              'cubic_Ta_LLZO','argyrodite_Li6PS5Cl','Li3YCl6','Li2_5Y0_5Zr0_5Cl6','LiCoO2')
_ROOT=Path(__file__).resolve().parents[2]


def _ordered_probe(disordered):
    """Deterministic greedy Ewald ordering with split-site exclusion, not a ground state."""
    from rhombus.transport.bvse_parameters import oxidation_states
    states=oxidation_states();host_species=[];host_coords=[];mobile=[]
    mixed=[]
    for site in disordered:
        symbols={s.symbol for s in site.species}
        if symbols=={'Li'}:mobile.append(site.frac_coords)
        else:mixed.append(site)
    remaining={s:round(disordered.composition.element_composition[s]) for s in states if s!='Li'}
    # Explicitly pick one bounded anion ordering, keeping exact integer totals.
    for site in sorted(mixed,key=lambda s:(len(s.species),tuple(s.frac_coords))):
        options=sorted(site.species.items(),key=lambda v:(-v[1],v[0].symbol))
        symbol=next((sp.symbol for sp,p in options if remaining.get(sp.symbol,0)>0),None)
        if symbol is None:raise ValueError('no integer host ordering')
        remaining[symbol]-=1;host_species.append(Species(symbol,states[symbol]));host_coords.append(site.frac_coords)
    if any(remaining.values()):raise ValueError('host ordering composition mismatch')
    count=round(disordered.composition.element_composition['Li'])
    full=Structure(disordered.lattice,host_species+[Species('Li',1)]*len(mobile),host_coords+mobile)
    matrix=EwaldSummation(full,acc_factor=6).total_energy_matrix
    host_n=len(host_species);candidates=list(range(host_n,len(full)));selected=[]
    distances=full.distance_matrix
    for _ in range(count):
        valid=[i for i in candidates if all(distances[i,j]>=1.2 for j in selected)]
        if not valid:raise ValueError('no collision-free bounded Li ordering')
        best=min(valid,key=lambda i:(2*matrix[i,:host_n].sum()+matrix[i,i]+2*matrix[i,selected].sum(),i))
        selected.append(best);candidates.remove(best)
    child=Structure(full.lattice,[full[i].specie for i in list(range(host_n))+selected],
                    [full[i].frac_coords for i in list(range(host_n))+selected])
    targets=[full[i].frac_coords.tolist() for i in candidates]
    return child,{'vacant_fractional_targets':targets,'parent_mobile_fractional':[list(map(float,p)) for p in mobile],
                  'carrier_vacancy_fraction':len(targets)/len(mobile),'formal_charge_e':float(child.charge),
                  'ordering_scope':'GREEDY_EWALD_SPLIT_SITE_PROBE_NOT_EXPERIMENTAL_ORDERING'}


def load_archetype(name):
    if name not in ARCHETYPES:raise ValueError('unknown archetype')
    base=_ROOT/'data/benchmarks/known_material/structures'
    if name in ('Li3YCl6','Li2_5Y0_5Zr0_5Cl6','LiCoO2'):
        return {'name':name,'structure':None,'coordinate_status':'SOURCE_COORDINATES_UNAVAILABLE',
                'reason':'Lattice/space group or nominal formula alone does not determine experimental coordinates'}
    if name in ('cubic_Ta_LLZO','argyrodite_Li6PS5Cl'):
        ident='g5q' if name=='cubic_Ta_LLZO' else '122'
        path=_ROOT/'data/benchmarks/v3_static/step_a_inputs'/('obelix-train-'+ident+'.cif')
        expected=('ee989184389516015ca32f0c54a683364ddb57dbe25952a45378748e9eb0468a' if ident=='g5q'
                  else 'a9fe913c3a112ed6043fe57dd0e899368bbe16e1272455f9ae5d4265c28ee5cb')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('archetype source digest mismatch')
        disordered=Structure.from_file(path);structure,defect=_ordered_probe(disordered)
        return {'name':name,'structure':structure,'defect':defect,'source_sha256':expected,
                'coordinate_status':'ORDERED_PROBE_FROM_RANDOMIZED_SOURCE_TRAIN_CIF_NOT_EXPERIMENTAL_ORIGINAL',
                'source_li_count':float(disordered.composition.element_composition['Li']),
                'ordered_li_count':sum(s.specie.symbol=='Li' for s in structure)}
    filename=('cod/1008166-latest-freeze-v1.cif' if name=='gamma_LiAlO2' else
              'literature/tetragonal-llzo-awaka-2009-nd-v1.cif' if name=='tetragonal_LLZO' else
              'cod/9009060-latest-freeze-v1.cif')
    path=base/filename;structure=Structure.from_file(path);defect={}
    if name=='Li2S_vacancy':
        defect=seed_vacancies(structure)[0];structure=Structure.from_dict(defect['structure'])
    elif name=='Li2S_Cl_vacancy':
        structure=expand_supercell(structure)
        index=next(i for i,s in enumerate(structure) if s.specie.symbol=='S')
        defect=substitute_aliovalent(structure,site_index=index,dopant='Cl',dopant_charge=-1)[0]
        structure=Structure.from_dict(defect['structure'])
    return {'name':name,'structure':structure,'defect':defect,'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'coordinate_status':'DERIVED_DEFECT_PROBE' if defect else 'RETAINED_CIF'}
