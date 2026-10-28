"""Audit all repository CIFs and the ten canonical V3 archetypes, without fitting.

Output is an audit record, never an independent scientific qualification.
Run with: python -m scripts.benchmark.audit_v3_fixed_rmin --output /tmp/v3-static.json
"""
import argparse
import json
from pathlib import Path


def discover_cifs(root):
    """Seven retained source/literature CIFs plus all stored OBELiX samples."""
    experimental=sorted((root/'data/benchmarks/known_material/structures').rglob('*.cif'))
    obelix=sorted((root/'data/benchmarks/v3_static/step_a_inputs').rglob('*.cif'))
    return [('SOURCE_OR_LITERATURE_CIF',p) for p in experimental] + [
        ('OBELIX_RANDOMIZED_TRAIN_NOT_EXPERIMENTAL_ORIGINAL',p) for p in obelix]


def _evaluate(structure, *, defect=None, grid_dimension=24, mep_steps=1200):
    from rhombus.generation.defect_engine import decorate_charges
    from rhombus.transport.static_assessment import assess_charge_scaled_transport
    from rhombus.pipeline.funnel import RhombusDiscoveryFunnel

    # Uniform canonical parameters. No material-name-dependent corrections.
    s=decorate_charges(structure)
    result=assess_charge_scaled_transport(s,defect=defect or {},
                                          grid_dimension=grid_dimension,mep_steps=mep_steps)
    # Hull/ESW are deliberately unavailable without independent reference energies.
    # H can be diagnosed on a converged high barrier, C needs other gate evidence.
    verdict=RhombusDiscoveryFunnel._static_verdict({'P0':{},'P1':{},'P0_5':result})
    return {'x_vac':result['vacancy_fraction'],
            'q_Li':result['charge_metadata']['q_Li'],
            'raw_channel_ev':result['raw_barriers_ev']['channel_3d'],
            'raw_hop_ev':result['raw_barriers_ev']['hop'],
            'raw_combined_ev':result['raw_barriers_ev']['combined'],
            'normalized_channel_ev':result['valence_normalized_barriers_ev']['channel_3d'],
            'normalized_hop_ev':result['valence_normalized_barriers_ev']['hop'],
            'normalized_combined_ev':result['valence_normalized_barriers_ev']['combined'],
            'neb_converged':bool(result['mep']['converged']),
            'endpoint_stationary':bool(result['mep']['endpoint_stationary']),
            'sub_occupied_void_detected':bool(result['frenkel'].get('sub_occupied_void_detected',False)),
            'raw_interstitial_minus_occupied_ev':result['frenkel'].get('raw_interstitial_minus_occupied_ev'),
            'static_model_only':verdict,'hull_mev_atom':None,'esw_volts':None,
            'qualification':'ABSTAIN'}


def audit(root, *, grid_dimension=24, mep_steps=1200):
    from pymatgen.core import Structure
    from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
    from rhombus.domain.archetypes import ARCHETYPES,build_archetype_a3

    def row_for(s, provenance, label, defect=None):
        row={'identifier':label,'provenance':provenance,'formula':None,
             'space_group':None,'atom_count':None,'status':'NOT_COMPUTED'}
        try:
            if s is None:raise ValueError('missing complete structure')
            row['formula']=s.composition.reduced_formula
            row['atom_count']=len(s)
            if not s.is_ordered:
                raise ValueError('partial occupancy requires a source-independent ordering rule')
            try:row['space_group']=SpacegroupAnalyzer(s).get_space_group_symbol()
            except (ValueError,TypeError):pass
            row.update(_evaluate(s,defect=defect,grid_dimension=grid_dimension,
                                 mep_steps=mep_steps))
            row['status']='EVALUATED'
        except (ValueError,RuntimeError,TypeError,KeyError,IndexError,ImportError) as exc:
            row.update(status='UNSUPPORTED_OR_FAILED',reason=f'{type(exc).__name__}: {exc}')
        return row

    cifs=[]
    for provenance,path in discover_cifs(root):
        label=path.relative_to(root).as_posix()
        try:
            structure=Structure.from_file(str(path))
            cifs.append(row_for(structure,provenance,label))
        except (ValueError,TypeError,RuntimeError) as exc:
            cifs.append({'identifier':label,'provenance':provenance,'status':'CIF_PARSE_FAILED',
                         'reason':f'{type(exc).__name__}: {exc}','qualification':'ABSTAIN'})
    archetypes=[]
    for name in ARCHETYPES:
        try:
            info=build_archetype_a3(name,allow_idealized_completion=True)
            archetypes.append(row_for(info['structure'],info.get('coordinate_status','UNSPECIFIED'),
                                      name,info.get('defect',{})))
        except (ValueError,RuntimeError,TypeError,KeyError,IndexError) as exc:
            archetypes.append({'identifier':name,'status':'ARCHETYPE_BUILD_FAILED',
                               'reason':f'{type(exc).__name__}: {exc}','qualification':'ABSTAIN'})
    return {'schema_version':'rhombus-v3-fixed-rmin-audit-v1',
            'reference_commit':'f5ce26abc34fe40f63b61a394483b212504c078f',
            'model':'UNQUALIFIED_CHARGE_BALANCED_FIXED_RMIN_PAIRWISE',
            'valence_share_factor':0.5,'per_file_tuning':False,
            'hull_esw_note':'null: no independent common-energy phase references supplied',
            'cifs':cifs,'canonical_archetypes':archetypes}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--grid-dimension',type=int,default=24)
    p.add_argument('--mep-steps',type=int,default=1200)
    args=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    result=audit(root,grid_dimension=args.grid_dimension,mep_steps=args.mep_steps)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('source CIF:',len([r for r in result['cifs'] if r['provenance']=='SOURCE_OR_LITERATURE_CIF']))
    print('OBELiX randomized CIF:',len([r for r in result['cifs'] if r['provenance'].startswith('OBELIX_')]))
    print('canonical structures:',len(result['canonical_archetypes']))
    print('audit:',args.output)


if __name__=='__main__':
    main()
