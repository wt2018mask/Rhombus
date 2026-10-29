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
    from rhombus.generation.defect_engine import order_mobile_sites
    row=order_mobile_sites(full,mobile_count=count)
    return Structure.from_dict(row['structure']),row


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


def audit_prompt_coordinates():
    """Check the supplied table in its stated setting without repairing it silently."""
    from pymatgen.core import Lattice
    argy=Structure.from_spacegroup(216,Lattice.cubic(9.859),['P','S','Cl','S'],
                                   [[.5,.5,.5],[.25,.25,.25],[0,0,0],[.1195,.1195,.1195]])
    p=[i for i,s in enumerate(argy) if s.specie.symbol=='P'];s=[i for i,a in enumerate(argy) if a.specie.symbol=='S']
    halide=Lattice.hexagonal(11.203,6.032)
    multiplicities=[len(Structure.from_spacegroup(164,halide,['Cl'],[v])) for v in ([1/3,0,.25],[1/3,2/3,.25])]
    return {'argyrodite_nearest_P_S_A':float(argy.distance_matrix[np.ix_(p,s)].min()),
            'halide_supplied_Cl_orbit_multiplicities':multiplicities,
            'halide_required_Cl_count':18,'complete_experimental_tables_supplied':False}


def build_archetype_a2(name, *, allow_idealized_completion=False):
    """Build owner-table inputs; incomplete sources require explicit hypothesis mode.

    A DOI supplied in a prompt is an attribution claim, not authenticated table
    bytes. Model completions below are deliberately NOT experimental originals.
    """
    from pymatgen.core import Lattice
    from rhombus.generation.defect_engine import order_mobile_sites
    if name not in ARCHETYPES:raise ValueError('unknown archetype')
    if name in ('gamma_LiAlO2','Li2S','Li2S_vacancy','Li2S_Cl_vacancy','tetragonal_LLZO'):
        result=load_archetype(name)
        if name=='Li2S':result['structure']=expand_supercell(result['structure'])
        return result
    if name=='LiCoO2':
        structure=Structure.from_spacegroup(166,Lattice.hexagonal(2.8156,14.0542),
                    [Species('Li',1),Species('Co',3),Species('O',-2)],[[0,0,0],[0,0,.5],[0,0,.2395]])
        return {'name':name,'structure':structure,'defect':{},
                'coordinate_status':'COMPLETE_OWNER_SUPPLIED_TABLE_NOT_INDEPENDENTLY_AUTHENTICATED',
                'claimed_doi':'10.1006/jssc.1998.7966'}
    if not allow_idealized_completion:
        raise ValueError('incomplete/inconsistent experimental table; explicit idealized completion required')
    if name=='cubic_Ta_LLZO':
        lattice=Lattice.cubic(12.928)
        host=Structure.from_spacegroup(230,lattice,[Species('La',3),Species('Zr',4),Species('O',-2)],
                                         [[0,.25,.125],[0,0,0],[.100,.196,.282]])
        zr=[i for i,s in enumerate(host) if s.specie.symbol=='Zr'];selected=[zr[0]]
        for _ in range(3):selected.append(max((i for i in zr if i not in selected),key=lambda i:(min(host.get_distance(i,j) for j in selected),-i)))
        for i in selected:host.replace(i,Species('Ta',5))
        # Li coordinates from retained experimental Al-garnet COD 7215448;
        # transferring them to Ta chemistry is a hybrid structural hypothesis.
        li=Structure.from_spacegroup(230,lattice,['Li','Li'],[[-.125,0,.25],[.1004,.6853,.5769]])
        for site in li:host.append({Species('Li',1):52/len(li)},site.frac_coords)
        defect=order_mobile_sites(host,mobile_count=52)
        return {'name':name,'structure':Structure.from_dict(defect['structure']),'defect':defect,
                'coordinate_status':'HYBRID_OWNER_FRAMEWORK_COD_LI_COORDINATES_NOT_EXPERIMENTAL_TA_REFINEMENT',
                'claimed_doi':'10.1016/j.ssi.2012.01.009','li_coordinate_source':'COD7215448',
                'site_population_override':52}
    if name=='argyrodite_Li6PS5Cl':
        lattice=Lattice.cubic(9.859)
        host=Structure.from_spacegroup(216,lattice,[Species('P',5),Species('S',-2),Species('Cl',-1),Species('S',-2)],
                                         [[.5,.5,.5],[.25,.25,.25],[0,0,0],[.3805,.3805,.3805]])
        # .1195 belongs to a different P-origin convention. Use an explicit
        # geometry correction to restore 2.04 A P-S bonds, not a paper claim.
        cage=Structure.from_spacegroup(216,lattice,['Li','Li'],[[.45,.25,.25],[.50,.25,.25]])
        for site in cage:host.append({Species('Li',1):24/len(cage)},site.frac_coords)
        defect=order_mobile_sites(host,mobile_count=24)
        return {'name':name,'structure':Structure.from_dict(defect['structure']),'defect':defect,
                'coordinate_status':'ORIGIN_CORRECTED_HOST_IDEALIZED_LI_CAGES_NOT_EXPERIMENTAL_REFINEMENT',
                'claimed_doi':'10.1021/jacs.7b06327','assumed_Li_orbits':[[.45,.25,.25],[.50,.25,.25]],
                'S16e_origin_correction':.3805}
    lattice=Lattice.hexagonal(11.203,6.032)
    primitive=Structure(Lattice.hexagonal(11.203/3,6.032),[Species('Cl',-1)]*2,[[1/3,2/3,.25],[2/3,1/3,.75]])
    primitive.make_supercell([3,3,1])
    host=Structure(lattice,[Species('Cl',-1)]*18,primitive.frac_coords)
    yttrium=[[0,0,0],[1/3,2/3,.5],[2/3,1/3,.5]]
    for point in yttrium:host.append(Species('Y',3),point)
    sites=[[i/3,j/3,z] for z in (0.,.5) for i in range(3) for j in range(3)]
    mobile=[p for p in sites if lattice.get_all_distances([p],yttrium).min()>1.]
    for point in mobile:host.append({Species('Li',1):9/len(mobile)},point)
    if name=='Li2_5Y0_5Zr0_5Cl6':
        host.make_supercell([2,1,1])
        indices=[i for i,s in enumerate(host) if s.is_ordered and s.specie.symbol=='Y']
        for i in indices[::2]:host.replace(i,Species('Zr',4))
        defect=order_mobile_sites(host,mobile_count=15)
    else:defect=order_mobile_sites(host,mobile_count=9)
    return {'name':name,'structure':Structure.from_dict(defect['structure']),'defect':defect,
            'coordinate_status':'IDEAL_HCP_COMPLETION_NOT_PUBLISHED_EXPERIMENTAL_CL_TABLE',
            'claimed_dois':['10.1002/adma.201803075','10.1002/zaac.19976230710'],
            'completion_basis':'IDEAL_3X3_HCP_CL_AND_OCTAHEDRAL_SITE_GRID'}


def build_archetype_a3(name, *, allow_idealized_completion=False):
    """A3 geometry hypotheses; DOI attribution still does not authenticate CIFs.

    The 48h argyrodite orbit is an explicit idealization, not a newly retrieved
    experimental refinement. All other A2 source identities are preserved.
    """
    if name!='argyrodite_Li6PS5Cl':
        return build_archetype_a2(name,allow_idealized_completion=allow_idealized_completion)
    if not allow_idealized_completion:
        raise ValueError('incomplete experimental table; explicit idealized completion required')
    from pymatgen.core import Lattice
    from rhombus.generation.defect_engine import order_mobile_sites
    lattice=Lattice.cubic(9.859)
    host=Structure.from_spacegroup(216,lattice,[Species('P',5),Species('S',-2),Species('Cl',-1),Species('S',-2)],
                                   [[.5,.5,.5],[.25,.25,.25],[0,0,0],[.3805,.3805,.3805]])
    # One 48h orbit, rather than two concentric 24g split-site copies. The
    # idealized u=.18 yields non-overlapping candidate sites at >=1.95 A.
    cage=Structure.from_spacegroup(216,lattice,['Li'],[[.18,.18,.02]])
    for site in cage:host.append({Species('Li',1):.5},site.frac_coords)
    defect=order_mobile_sites(host,mobile_count=24)
    defect['nominal_empty_site_fraction']=.5
    return {'name':name,'structure':Structure.from_dict(defect['structure']),'defect':defect,
            'coordinate_status':'ORIGIN_CORRECTED_HOST_IDEALIZED_48H_NOT_EXPERIMENTAL_REFINEMENT',
            'assumed_Li_orbits':[[.18,.18,.02]],'S16e_origin_correction':.3805,
            'claimed_doi':'10.1021/jacs.7b06327','qualification':'ABSTAIN'}
