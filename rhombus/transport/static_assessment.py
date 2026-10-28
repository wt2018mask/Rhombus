"""Reproducible static diagnostics on actual coordinates, with explicit limits."""
import hashlib
import json
import math
import numpy as np
from .bvse_parameters import build_site_evaluator, host_radii, parameter_identity
from .bvse_percolation import percolation_thresholds
from .neb_pathway import ClimbingImageMEPSolver


def assess_vacancy_transport_a2(structure, *, defect=None, grid_dimension=None, spacing_A=.22,
                               born_amplitude_eV=1., polarizability=None, dielectric_constant=9.,mep_steps=1200):
    """Endpoint-relaxed vacancy migration plus a separately retained Frenkel proxy.

    B/radii/alpha/dielectric inputs define an uncalibrated Hamiltonian. They are
    never fitted to target labels here. An attractive defect binding correction
    has NEGATIVE sign; adding an arbitrary positive binding penalty is forbidden.
    """
    from .bvse_parameters import ANIONS,CATIONS
    from .bvse_percolation import SiteEnergyEvaluator,SpectatorSiteEnergyEvaluator
    from .neb_pathway import initialize_relaxed_pathway,refine_path_saddle,relax_endpoint_local_basin
    if not structure.is_ordered or not 1<len(structure)<=512:raise ValueError('bounded ordered structure required')
    if not np.isfinite(born_amplitude_eV) or born_amplitude_eV<0 or not np.isfinite(dielectric_constant) or dielectric_constant<=0:
        raise ValueError('explicit finite Born/dielectric model parameters required')
    if grid_dimension is not None and not 8<=grid_dimension<=64:raise ValueError('bounded grid required')
    defect=defect or {};mobile=[i for i,s in enumerate(structure) if s.specie.symbol=='Li']
    if len(mobile)<2:raise ValueError('at least two mobile sites required')
    alpha={'O':1.,'S':.35,'Cl':.35} if polarizability is None else dict(polarizability)
    if any(not np.isfinite(v) or not 0<v<=1 for v in alpha.values()):raise ValueError('polarizability factors in (0,1] required')
    cations=dict(CATIONS,Co=(3,.545))
    anions={s:(v[1],v[2],v[0]) for s,v in ANIONS.items()}
    repulsion={s:(q,.76+r,r) for s,(q,r) in cations.items() if s!='Li'}
    radii={**{s:v[3] for s,v in ANIONS.items()},**{s:v[1] for s,v in cations.items() if s!='Li'}}
    born={s:(born_amplitude_eV*alpha.get(s,1.),.76+r,.29) for s,r in radii.items()} if born_amplitude_eV>0 else {}
    contacts={s:.76+r for s,(q,r) in cations.items() if s!='Li'}
    def host(s):return SiteEnergyEvaluator(s,anions=anions,cations=repulsion,pauli=False,
                 shell_stiffness={'O':20.,'S':8.,'Cl':8.},shell_max_A=.15,periodic_cutoff_A=8.,
                 born_mayer=born,unscreened_contacts=contacts)
    bounds={'min_dimension':grid_dimension or 8,'max_dimension':grid_dimension or 64}
    bare=build_site_evaluator(structure,periodic_cutoff_A=8.) if 'Co' not in {s.specie.symbol for s in structure} else SiteEnergyEvaluator(
        structure,anions=anions,cations=repulsion,pauli=False,periodic_cutoff_A=8.)
    channel=percolation_thresholds(bare.grid(spacing_A,**bounds))['barriers_eV']['3D']
    xvac=float(defect.get('stoichiometric_vacancy_fraction',defect.get('carrier_vacancy_fraction',0.)))
    if not np.isfinite(xvac) or not 0<=xvac<1:raise ValueError('bounded vacancy fraction required')
    extrinsic=xvac>=.01
    probe=structure.copy()
    if extrinsic:
        targets=np.asarray(defect.get('vacant_fractional_targets',[]),float)
    else:
        target=probe[mobile[0]].frac_coords.copy();probe.remove_sites([mobile[0]]);targets=np.array([target])
    if targets.ndim!=2 or targets.shape[1]!=3 or not len(targets) or not np.isfinite(targets).all():raise ValueError('explicit vacancy target required')
    candidates=[i for i,s in enumerate(probe) if s.specie.symbol=='Li'];points=[probe[i].frac_coords for i in candidates]
    distances=probe.lattice.get_all_distances(targets,points);options=[]
    hostpoints=[s.frac_coords for s in probe if s.specie.symbol!='Li']
    for k,t in enumerate(targets):
        if probe.lattice.get_all_distances([t],hostpoints).min()<1.:continue
        for j,i in enumerate(candidates):
            others=np.delete(distances[k],j)
            if distances[k,j]>.5 and (not len(others) or others.min()>=1.95-1e-8):options.append((distances[k,j],i,k))
    if not options:raise ValueError('no Pauli-feasible single-ion vacancy hop')
    _,active,target_index=min(options);target=targets[target_index]
    evaluator=SpectatorSiteEnergyEvaluator(probe,active,host(probe),periodic_cutoff_A=8.)
    field=evaluator.grid(spacing_A,**bounds)
    _,image=probe.lattice.get_distance_and_image(probe[active].frac_coords,target)
    nominal_end=probe.lattice.get_cartesian_coords(target+image)
    path=initialize_relaxed_pathway(field,probe.lattice,probe[active].coords,nominal_end,evaluator,images=17)
    endpoints=path['endpoint_relaxations'];start,end=[e['position_A'] for e in endpoints]
    mep=ClimbingImageMEPSolver().solve(start,end,evaluator,images=17,initial_path=path['positions_A'],
          optimizer='fire',max_step_A=.05,step_size=.01,max_steps=mep_steps,force_tolerance=.03)
    peak=refine_path_saddle(mep['positions_A'],evaluator);migration=peak['barrier_ev']
    mep.update(band_converged=mep['converged'],endpoint_relaxations=endpoints,endpoint_stationary=path['endpoint_stationary'],
               converged=bool(mep['converged'] and path['endpoint_stationary']),saddle_refinement=peak,dense_path_barrier_ev=migration)
    frenkel={'required':not extrinsic,'formation_energy_is_model_proxy':True};generation=0.
    if not extrinsic:
        creator=SpectatorSiteEnergyEvaluator(structure,mobile[0],host(structure),periodic_cutoff_A=8.)
        initial=relax_endpoint_local_basin(structure[mobile[0]].coords,creator)
        landscape=creator.grid(spacing_A,**bounds);shape=np.array(landscape.shape)
        order=np.argsort(landscape.ravel());void=None
        for batch in np.array_split(order,max(1,len(order)//1024)):
            frac=np.array(np.unravel_index(batch,landscape.shape)).T/shape
            d=structure.lattice.get_all_distances(frac,structure.frac_coords)
            valid=np.where(d.min(axis=1)>=1.2)[0]
            if len(valid):void=frac[valid[0]];break
        if void is None:raise ValueError('no resolved Frenkel interstitial')
        final=relax_endpoint_local_basin(structure.lattice.get_cartesian_coords(void),creator)
        distance=float(structure.lattice.get_distance_and_image(structure.lattice.get_fractional_coords(initial['position_A']),
                    structure.lattice.get_fractional_coords(final['position_A']))[0])
        binding=-14.3996454784255/(dielectric_constant*distance) if distance>.5 else 0.
        delta=final['energy_eV']-initial['energy_eV'];generation=.5*max(0.,delta+binding)
        frenkel.update(initial=initial,interstitial=final,separation_A=distance,site_energy_difference_eV=delta,
                       dielectric_constant=dielectric_constant,binding_correction_eV=binding,
                       pair_energy_proxy_eV=max(0.,delta+binding),stationary=initial['stationary'] and final['stationary'] and distance>.5,
                       binding_scope='DECLARED_DIELECTRIC_CORRECTION_POSSIBLE_DOUBLE_COUNTING_NOT_CALIBRATED')
    return {'schema_version':'rhombus-vacancy-transport-a2','vacancy_fraction':xvac,'host_channel_barrier_3d_ev':channel,
            'spectator_caged_hop_barrier_ev':migration,'vacancy_migration_barrier_ev':migration,
            'effective_activation_barrier_ev':migration+generation,'defect_generation_penalty_ev':generation,
            'migration_probe_mobile_count':len(candidates),'spectator_count':len(candidates)-1,
            'mechanism':'EXTRINSIC_VACANCY' if extrinsic else 'TEMPORARY_VACANCY_HOP_PLUS_SEPARATE_FRENKEL_PROXY',
            'frenkel':frenkel,'mep':mep,'initialization':path,'grid_shape':list(field.shape),
            'model_parameters':{'born_amplitude_eV':born_amplitude_eV,'born_decay_A':.29,'polarizability':alpha,
                                'dielectric_constant':dielectric_constant,'Co_radius_A':.545},
            'model_applicability':'UNQUALIFIED','qualification':'ABSTAIN'}



def assess_vacancy_transport_a3(structure, *, defect=None, grid_dimension=None, spacing_A=.22,mep_steps=1200):
    """A3 pure-Morse vacancy diagnostic; raw host-only Frenkel differences retained."""
    from .bvse_percolation import build_softbv_evaluator,SpectatorSiteEnergyEvaluator
    from .neb_pathway import initialize_relaxed_pathway,refine_path_saddle
    if not structure.is_ordered or not 1<len(structure)<=512:raise ValueError('bounded ordered structure required')
    if grid_dimension is not None and not 8<=grid_dimension<=64:raise ValueError('bounded grid required')
    if not np.isfinite(spacing_A) or not .15<=spacing_A<=.5:raise ValueError('bounded spacing required')
    defect=defect or {};mobile=[i for i,a in enumerate(structure) if a.specie.symbol=='Li']
    if len(mobile)<2:raise ValueError('at least two mobile sites required')
    bounds={'min_dimension':grid_dimension or 8,'max_dimension':grid_dimension or 64}
    # A primitive layered cell can represent an in-plane Li neighbor only as
    # its own periodic image. Resolve a DISTINCT atom before removing a vacancy.
    nominal=structure.distance_matrix[np.ix_(mobile,mobile)]+np.eye(len(mobile))*1e6
    expansion=[2 if length<4.2 else 1 for length in structure.lattice.abc]
    if nominal.min()>4.2 and expansion!=[1,1,1] and not defect:
        expanded=structure.copy();expanded.make_supercell(expansion)
        result=assess_vacancy_transport_a3(expanded,grid_dimension=grid_dimension,spacing_A=spacing_A,mep_steps=mep_steps)
        result.update(periodic_probe_expansion=expansion,input_atom_count=len(structure),
                      expanded_probe_structure=expanded.as_dict())
        return result
    host=build_softbv_evaluator(structure)
    host_field=host.grid(spacing_A,**bounds)
    host_result=percolation_thresholds(host_field)
    channel=host_result['barriers_eV']['3D']
    xvac=float(defect.get('stoichiometric_vacancy_fraction',defect.get('carrier_vacancy_fraction',0.)))
    if not np.isfinite(xvac) or not 0<=xvac<1:raise ValueError('bounded vacancy fraction required')
    extrinsic=xvac>=.01
    probe=structure.copy()
    if extrinsic:
        targets=np.asarray(defect.get('vacant_fractional_targets',[]),float)
    else:
        target=probe[mobile[0]].frac_coords.copy();probe.remove_sites([mobile[0]]);targets=np.array([target])
    if targets.ndim!=2 or targets.shape[1]!=3 or not len(targets) or not np.isfinite(targets).all():raise ValueError('explicit vacancy target required')
    candidates=[i for i,s in enumerate(probe) if s.specie.symbol=='Li'];points=[probe[i].frac_coords for i in candidates]
    distances=probe.lattice.get_all_distances(targets,points);options=[]
    hostpoints=[s.frac_coords for s in probe if s.specie.symbol!='Li']
    for k,t in enumerate(targets):
        if probe.lattice.get_all_distances([t],hostpoints).min()<1.:continue
        for j,i in enumerate(candidates):
            others=np.delete(distances[k],j)
            if distances[k,j]>.5 and (not len(others) or others.min()>=1.95-1e-8):options.append((distances[k,j],i,k))
    if not options:raise ValueError('no Pauli-feasible single-ion vacancy hop')
    rejected=[];path=None
    # Never select a near-coincident split-site self-hop. Try distinct neighbors
    # in geometric order, retaining every rejection rather than masking failure.
    for distance,active,target_index in sorted(options):
        if not (2.<=distance<=4.2 and (extrinsic or 2.2<=distance<=3.8)):continue
        target=targets[target_index]
        evaluator=SpectatorSiteEnergyEvaluator(probe,active,build_softbv_evaluator(probe),periodic_cutoff_A=8.)
        _,image=probe.lattice.get_distance_and_image(probe[active].frac_coords,target)
        nominal_end=probe.lattice.get_cartesian_coords(target+image)
        try:
            # Relax/check endpoints before paying for a voxel graph search.
            from .neb_pathway import relax_endpoint_local_basin
            pre=[relax_endpoint_local_basin(p,evaluator,radius_A=.65,boundary='soft')
                 for p in (probe[active].coords,nominal_end)]
            relaxed=probe.lattice.get_distance_and_image(*[probe.lattice.get_fractional_coords(e['position_A']) for e in pre])[0]
            if not 2.<=relaxed<=4.2:raise ValueError('relaxed endpoints collapsed or outside distinct hop distance range')
            field=evaluator.grid(spacing_A,**bounds)
            path=initialize_relaxed_pathway(field,probe.lattice,probe[active].coords,nominal_end,evaluator,
                     images=17,basin_radius_A=.65,boundary='soft',separation_range_A=(2.,4.2))
        except ValueError as error:
            rejected.append({'active_index':active,'target_index':target_index,'reason':str(error)})
            if len(rejected)>=16:break
            continue
        break
    if path is None:raise ValueError('no distinct relaxed vacancy hop: '+str(rejected))
    path['rejected_neighbors']=rejected
    endpoints=path['endpoint_relaxations'];start,end=[e['position_A'] for e in endpoints]
    mep=ClimbingImageMEPSolver().solve(start,end,evaluator,images=17,initial_path=path['positions_A'],
          optimizer='fire',max_step_A=.05,step_size=.01,max_steps=mep_steps,force_tolerance=.03)
    peak=refine_path_saddle(mep['positions_A'],evaluator);migration=peak['barrier_ev']
    mep.update(band_converged=mep['converged'],endpoint_relaxations=endpoints,endpoint_stationary=path['endpoint_stationary'],
               converged=bool(mep['converged'] and path['endpoint_stationary']),saddle_refinement=peak,dense_path_barrier_ev=migration)
    frenkel={'required':not extrinsic,'formation_energy_is_model_proxy':True,
             'site_energy_difference_eV':0.,'basis':'GENERATION_COST_NOT_APPLIED_EXISTING_VACANCY'};generation=0.
    if not extrinsic:
        frenkel=assess_host_frenkel_proxy(structure,host,host_field,host_result)
        generation=.5*frenkel['site_energy_difference_eV']
    return {'schema_version':'rhombus-vacancy-transport-a3','vacancy_fraction':xvac,'host_channel_barrier_3d_ev':channel,
            'spectator_caged_hop_barrier_ev':migration,'vacancy_migration_barrier_ev':migration,
            'effective_activation_barrier_ev':migration+generation,'defect_generation_penalty_ev':generation,
            'migration_probe_mobile_count':len(candidates),'spectator_count':len(candidates)-1,
            'mechanism':'EXTRINSIC_VACANCY' if extrinsic else 'TEMPORARY_VACANCY_HOP_PLUS_SEPARATE_FRENKEL_PROXY',
            'frenkel':frenkel,'mep':mep,'initialization':path,'grid_shape':list(field.shape),
            'model_parameters':{'anion_born_mayer_scale':0.,'screening_factor':.75,'periodic_cutoff_A':8.},
            'activation_proxy_valid':bool(frenkel['site_energy_difference_eV']>=0 and mep['converged']),
            'parameter_identity':parameter_identity(),
            'model_applicability':'UNQUALIFIED','qualification':'ABSTAIN'}


def assess_caged_transport(structure, *, vacancy_targets=(), spacing_A=.22, grid_dimension=None,
                          shell_stiffness=None, shell_max_A=.15, mep_steps=600):
    """Active-ion defect probe, kept separate from the historical bare-host model.

    Site-energy differences are NOT many-body Frenkel formation energies.
    Shell stiffnesses are modeling inputs, not experimentally calibrated values.
    """
    from scipy.optimize import minimize
    from .bvse_percolation import SpectatorSiteEnergyEvaluator
    from .neb_pathway import initialize_pathway_from_voxel_grid
    if not structure.is_ordered or len(structure)>512:
        raise ValueError('bounded ordered structure required')
    if not math.isfinite(spacing_A) or not .15<=spacing_A<=.5:
        raise ValueError('bounded spatial resolution required')
    if grid_dimension is not None and not 8<=grid_dimension<=64:
        raise ValueError('bounded diagnostic grid required')
    mobile=[i for i,s in enumerate(structure) if s.specie.symbol=='Li']
    if not mobile:raise ValueError('mobile Li required')
    targets=np.asarray(vacancy_targets,float)
    if targets.size and (targets.ndim!=2 or targets.shape[1]!=3 or not np.isfinite(targets).all()):
        raise ValueError('finite vacancy targets required')
    if targets.size:
        if structure.lattice.get_all_distances(targets,structure.frac_coords).min()<.5:
            raise ValueError('vacancy target occupied or overlapping host')
        # Split crystallographic positions near an occupied spectator are not
        # independent vacant hopping targets. Check the N-1 geometry first.
        distances=structure.lattice.get_all_distances(targets,[structure[i].frac_coords for i in mobile])
        options=[]
        for k,t in enumerate(targets):
            for j,i in enumerate(mobile):
                remaining=np.delete(distances[k],j)
                if not len(remaining) or remaining.min()>=1.2:
                    options.append((distances[k,j],i,k))
        if not options:raise ValueError('no vacancy target free of occupied spectator split sites')
        _,active,tgt=min(options)
        target=targets[tgt]
    else:active=mobile[0];target=None
    bare=build_site_evaluator(structure,periodic_cutoff_A=8.)
    # Opt-in shell model; old bare-host regression remains byte compatible.
    from .bvse_parameters import ANIONS,CATIONS
    from .bvse_percolation import SiteEnergyEvaluator
    stiffness={'O':20.,'S':8.,'Cl':8.} if shell_stiffness is None else shell_stiffness
    shell=SiteEnergyEvaluator(structure,anions={s:(v[1],v[2],v[0]) for s,v in ANIONS.items()},
                               cations={s:(q,.76+r,r) for s,(q,r) in CATIONS.items() if s!='Li'},
                               pauli=False,shell_stiffness=stiffness,shell_max_A=shell_max_A,periodic_cutoff_A=8.)
    spectator=SpectatorSiteEnergyEvaluator(structure,active,shell,periodic_cutoff_A=8.)
    bounds={'min_dimension':grid_dimension or 8,'max_dimension':grid_dimension or 64}
    host_field=bare.grid(spacing_A,**bounds)
    host=percolation_thresholds(host_field)
    field=spectator.grid(spacing_A,**bounds)
    shape=np.array(field.shape)
    start=structure[active].coords
    if target is None:
        # Search geometrically distinct interstitial voids, not the vacated
        # active equilibrium site. Distances are a search constraint, not an
        # arbitrary energy penalty tuned to a desired material ordering.
        order=np.argsort(field.ravel())
        target=None
        for batch in np.array_split(order, max(1,len(order)//1024)):
            frac=np.array(np.unravel_index(batch,field.shape)).T/shape
            distances=structure.lattice.get_all_distances(frac,structure.frac_coords)
            valid=np.where(distances.min(axis=1)>=1.2)[0]
            if len(valid):target=frac[valid[0]];break
        if target is None:raise ValueError('no resolved interstitial void')
        # SLSQP local sub-voxel refinement with the same explicit void constraint.
        cart=structure.lattice.get_cartesian_coords(target)
        objective=lambda p:(float(spectator([p])[0][0]),-spectator([p])[1][0])
        def clear(p):
            return structure.lattice.get_all_distances([structure.lattice.get_fractional_coords(p)],structure.frac_coords)[0]-1.2
        opt=minimize(objective,cart,jac=True,method='SLSQP',constraints={'type':'ineq','fun':clear},options={'maxiter':80,'ftol':1e-9})
        if opt.success and clear(opt.x).min()>-1e-6:target=structure.lattice.get_fractional_coords(opt.x)
    _,image=structure.lattice.get_distance_and_image(structure[active].frac_coords,target)
    end=structure.lattice.get_cartesian_coords(target+image)
    path=initialize_pathway_from_voxel_grid(field,structure.lattice,start,end,images=17)
    result=ClimbingImageMEPSolver().solve(start,end,spectator,images=17,initial_path=path['positions_A'],
                                         optimizer='fire',max_step_A=.05,step_size=.01,max_steps=mep_steps,force_tolerance=.03)
    # Actual continuous evaluations at many points expose sub-image spikes.
    from .neb_pathway import resample_pathway,refine_path_saddle
    dense=resample_pathway(result['positions_A'],257)
    dense_energy=spectator(dense)[0]
    dense_barrier=float(dense_energy.max()-dense_energy[0])
    refined=refine_path_saddle(result['positions_A'],spectator)
    dense_barrier=max(dense_barrier,refined['barrier_ev'])
    result['saddle_refinement']=refined
    result['dense_path_barrier_ev']=dense_barrier
    result['image_saddle_sampling_error_ev']=abs(dense_barrier-result['barrier_ev'])
    if result['image_saddle_sampling_error_ev']>.03:result['converged']=False
    xvac=len(targets)/(len(mobile)+len(targets)) if targets.size else 0.
    delta=float(spectator([end])[0][0]-spectator([start])[0][0])
    generation=0. if xvac>=.015 else max(0.,delta)/2
    return {'schema_version':'rhombus-caged-static-v1','host_channel_barrier_3d_ev':host['barriers_eV']['3D'],
            'spectator_caged_hop_barrier_ev':dense_barrier,'effective_activation_barrier_ev':dense_barrier+generation,
            'defect_generation_penalty_ev':generation,'defect_generation_scope':'HALF_TEST_ION_SITE_ENERGY_DIFFERENCE_NOT_FRENKEL_FORMATION_ENERGY',
            'vacancy_fraction':xvac,'active_index':active,'spectator_count':len(mobile)-1,
            'target_fractional':list(map(float,target)),'target_kind':'VACANCY' if targets.size else 'CONSTRAINED_INTERSTITIAL_VOID',
            'grid_shape':list(field.shape),'actual_spacing_A':(np.array(structure.lattice.abc)/shape).tolist(),
            'periodic_cutoff_A':8.,'cutoff_switch':'C2_SMOOTH_LAST_1_ANGSTROM',
            'initialization':path,'mep':result,'shell_stiffness_eV_A2':stiffness,'shell_max_A':shell_max_A,
            'parameter_identity':parameter_identity(),'model_applicability':'UNQUALIFIED',
            'qualification':'ABSTAIN'}


def assess_static_transport(structure, *, grid_dimension=24, screening_factor=1.,
                            effective_charge_scale=1., max_barrier_eV=1., run_mep=True,
                            vacancy_fractional_target=None, mep_steps=200):
    if not 4 <= grid_dimension <= 40 or not math.isfinite(max_barrier_eV) or max_barrier_eV <= 0:
        raise ValueError('bounded grid and explicit positive barrier policy required')
    evaluator = build_site_evaluator(structure, screening_factor=screening_factor,
                                     effective_charge_scale=effective_charge_scale)
    field = evaluator.grid(min_dimension=grid_dimension, max_dimension=grid_dimension)
    result = percolation_thresholds(field, lattice=structure.lattice,
                                    host_fractional=[s.frac_coords for s in evaluator.sites],
                                    host_radii_A=host_radii(structure))
    barrier = result['barriers_eV']['3D']
    rejected = barrier is not None and barrier > max_barrier_eV
    result.update(decision='REJECT' if rejected else 'CONTINUE',
                  gate_verdict='FALSIFIED_HIGH_STATIC_BARRIER' if rejected else 'PASS_P0_5',
                  gate_scope='PROVISIONAL_OWNER_MODEL_POLICY_NOT_MATERIAL_CALIBRATION',
                  threshold_eV=max_barrier_eV, parameter_identity=parameter_identity(),
                  screening_factor=screening_factor, effective_charge_scale=effective_charge_scale,
                  structure_sha256=hashlib.sha256(json.dumps(structure.as_dict(), sort_keys=True).encode()).hexdigest())
    result['mep'] = None
    if run_mep:
        mobile = [s for s in structure if s.specie.symbol == 'Li']
        if len(mobile) < 2 and vacancy_fractional_target is None:
            raise ValueError('two mobile sites or an explicit vacancy target required')
        if vacancy_fractional_target is not None:
            target = np.asarray(vacancy_fractional_target, float)
            if target.shape != (3,) or not np.isfinite(target).all():
                raise ValueError('finite fractional vacancy target required')
            start = min(mobile, key=lambda s: structure.lattice.get_distance_and_image(s.frac_coords, target)[0])
            _, image = structure.lattice.get_distance_and_image(start.frac_coords, target)
            end = structure.lattice.get_cartesian_coords(target+image)
        else:
            distance, i, j, image = min((
                (lambda d: (d[0], i, j, d[1]))(structure.lattice.get_distance_and_image(a.frac_coords, b.frac_coords))
                for i, a in enumerate(mobile) for j, b in enumerate(mobile) if j > i), key=lambda p: p[:3])
            start = mobile[i]
            end = structure.lattice.get_cartesian_coords(mobile[j].frac_coords+image)
        mep = ClimbingImageMEPSolver().solve(start.coords, end, evaluator, max_steps=mep_steps,
                                             step_size=.005, force_tolerance=.05)
        mep['scope'] = 'FIXED_HOST_TEST_ION_MORSE_MODEL_NO_MANY_ION_EXCLUSION_OR_MLIP'
        result['mep'] = mep
    return result


def assess_host_frenkel_proxy(structure,host,field,percolation):
    """Host-well difference, not a measured many-body Frenkel formation energy.

    Independent local minima must remain clear of ALL nominal Li/host sites
    after relaxation. No constrained boundary point is called a local minimum.
    A percolation saddle fallback is explicitly a saddle proxy, not a defect.
    """
    from scipy.ndimage import minimum_filter
    from .neb_pathway import relax_endpoint_local_basin
    mobile=[s.frac_coords for s in structure if s.specie.symbol=='Li']
    hosts=[s.frac_coords for s in structure if s.specie.symbol!='Li']
    occupied=[relax_endpoint_local_basin(structure.lattice.get_cartesian_coords(p),host,
                  radius_A=.65,boundary='soft') for p in mobile]
    initial=min(occupied,key=lambda e:e['energy_eV'])
    indices=np.argwhere(field<=minimum_filter(field,size=3,mode='wrap'))
    indices=indices[np.argsort(field[tuple(indices.T)])]
    frac=indices/np.array(field.shape)
    def clear(points):
        return ((structure.lattice.get_all_distances(points,mobile).min(axis=1)>=1.85) &
                (structure.lattice.get_all_distances(points,hosts).min(axis=1)>=1.80))
    candidates=[]
    clear_pockets=frac[clear(frac)]
    for point in clear_pockets:
        final=relax_endpoint_local_basin(structure.lattice.get_cartesian_coords(point),host,radius_A=.65,boundary='soft')
        refined=structure.lattice.get_fractional_coords(final['position_A'])
        if final['stationary'] and clear([refined])[0]:candidates.append(final)
        if len(candidates)>=64:break
    if candidates:
        final=min(candidates,key=lambda e:e['energy_eV']);basis='SEPARATE_HOST_INTERSTITIAL_LOCAL_MINIMUM'
        energy=final['energy_eV']
    else:
        final=None;basis='NO_SEPARATE_MINIMUM_HOST_3D_PERCOLATION_SADDLE_PROXY'
        energy=percolation['minimum_energy_eV']+percolation['barriers_eV']['3D']
    delta=float(energy-initial['energy_eV'])
    return {'required':True,'formation_energy_is_model_proxy':True,'hamiltonian':'HOST_ONLY_PURE_MORSE_SCREENED_CATION_A3',
            'initial':initial,'interstitial':final,'interstitial_energy_eV':float(energy),
            'occupied_basin_count':len(occupied),'site_energy_difference_eV':delta,
            'grid_pockets_passing_clearance':len(clear_pockets),'retained_stationary_minima':len(candidates),
            'interstitial_search_limit':64,'interstitial_search_truncated':len(candidates)>=64,
            'pair_energy_proxy_eV':delta,'stationary':initial['stationary'] and (final is None or final['stationary']),
            'basis':basis,'binding_correction_eV':0.,'negative_energy_clipped':False,
            'model_applicability':'UNQUALIFIED','qualification':'ABSTAIN'}
