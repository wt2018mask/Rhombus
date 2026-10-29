"""Additive, provisional numerical diagnostics; never transport qualification."""
import numpy as np


def thermal_windows(trace, *, equilibration_fraction=0.25, degrees_of_freedom=None):
    if not 0 <= equilibration_fraction < 1:
        raise ValueError('invalid discard fraction')
    rows = [r for r in trace['samples'] if r['phase'] == 'production']
    rows = rows[int(len(rows)*equilibration_fraction):]
    if len(rows) < 3:
        raise ValueError('insufficient production samples')
    data = np.array([[r[k] for k in ('time_fs','temperature_K','potential_energy_eV','kinetic_energy_eV')] for r in rows],float)
    if not np.isfinite(data).all() or np.any(np.diff(data[:,0])<=0) or trace['atom_count']<=0:
        raise ValueError('invalid time or measurement')
    if np.any(data[:,1]<0) or np.any(data[:,3]<0):
        raise ValueError('negative temperature or kinetic energy')
    t = data[:,0]/1000
    mean = float(data[:,1].mean())
    ratio = float(data[:,1].std()/mean) if mean>0 else None
    if degrees_of_freedom is not None and (type(degrees_of_freedom) is not int or degrees_of_freedom<=0):
        raise ValueError('explicit positive degrees of freedom required')
    return {'schema_version':'rhombus-windowed-thermal-diagnostic-v1', 'sample_count':len(rows),
            'discarded_production_fraction':equilibration_fraction, 'mean_temp_k':mean,'temp_std_ratio':ratio,
            'post_eq_potential_drift_ev_per_atom_ps':float(np.polyfit(t-t[0],data[:,2]/trace['atom_count'],1)[0]),
            'kinetic_temperature_K':float(2*data[:,3].mean()/(degrees_of_freedom*8.617333262145e-5)) if degrees_of_freedom else None,
            'interpretation':'NVT trends alone cannot distinguish thermostat relaxation from numerical or physical instability',
            'qualification':'ABSTAIN'}


def multi_origin_msd(mobile, host, times_ps, *, host_limit_angstrom, hop_threshold_angstrom=1., minimum_hop_events=5):
    """Inputs must be unwrapped Cartesian coordinates in Angstrom; no PBC inference."""
    mobile,host,times = np.asarray(mobile,float),np.asarray(host,float),np.asarray(times_ps,float)
    if (mobile.ndim!=3 or host.ndim!=3 or mobile.shape[2]!=3 or host.shape[2]!=3
        or len(mobile)!=len(host) or len(times)!=len(host) or min(mobile.shape[1],host.shape[1])<1
        or len(times)<16 or not all(np.isfinite(a).all() for a in (mobile,host,times))
        or not np.allclose(np.diff(times),times[1]-times[0]) or times[1]<=times[0]
        or not np.isfinite(host_limit_angstrom) or not np.isfinite(hop_threshold_angstrom)
        or host_limit_angstrom<=0 or hop_threshold_angstrom<=0
        or type(minimum_hop_events) is not int or minimum_hop_events<1):
        raise ValueError('finite uniformly sampled unwrapped trajectories and positive limits required')
    drift=host.mean(axis=1)-host[0].mean(axis=0)
    corrected=mobile-drift[:,None,:]
    framework=host-host[0]-drift[:,None,:]
    rmsd=float(np.sqrt(np.mean(np.sum(framework**2,axis=2),axis=1)).max())
    def estimate(x):
        lags=np.arange(1,len(x)//4+1)
        msd=np.array([np.mean(np.sum((x[k:]-x[:-k])**2,axis=2)) for k in lags])
        valid=msd>1e-15
        beta=float(np.polyfit(np.log(lags[valid]),np.log(msd[valid]),1)[0]) if valid.sum()>=3 else None
        return beta,lags.tolist(),msd.tolist()
    beta,lags,msd=estimate(corrected)
    blocks=[estimate(x)[0] for x in np.array_split(corrected,2)]
    hops=int(np.sum(np.linalg.norm(np.diff(corrected,axis=0),axis=2)>hop_threshold_angstrom))
    if rmsd>host_limit_angstrom: regime='FRAMEWORK_INSTABILITY'
    elif beta is None: regime='INDETERMINATE'
    elif beta<.3: regime='VIBRATIONAL_CAGED'
    elif beta<.85 or hops<minimum_hop_events: regime='SUBDIFFUSIVE_TRANSIENT'
    elif beta<=1.15: regime='DIFFUSIVE_FICKIAN'
    else: regime='INDETERMINATE'
    return {'schema_version':'rhombus-multi-origin-msd-diagnostic-v1','regime':regime,'beta':beta,
            'lag_times_ps':[(times[1]-times[0])*k for k in lags],'msd_A2':msd,
            'block_beta_variance':float(np.var(blocks)) if all(b is not None for b in blocks) else None,
            'rmsd_host_max_angstrom':rmsd,'large_increment_events':hops,
            'event_interpretation':'Displacement increments are not independently confirmed site hops',
            'threshold_status':'PROVISIONAL','qualification':'ABSTAIN','conductivity_S_cm':None}
