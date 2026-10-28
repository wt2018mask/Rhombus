"""Reproducible static diagnostics on actual coordinates, with explicit limits."""
import hashlib
import json
import math
import numpy as np
from .bvse_parameters import build_site_evaluator, host_radii, parameter_identity
from .bvse_percolation import percolation_thresholds
from .neb_pathway import ClimbingImageMEPSolver


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
