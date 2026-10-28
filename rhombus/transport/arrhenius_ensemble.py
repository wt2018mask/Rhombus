"""Conditional Nernst-Einstein/Arrhenius estimates; no origin attestation."""
import numpy as np

KB_EV=8.617333262145e-5
KB_J=1.380649e-23
E_CHARGE=1.602176634e-19


def quantify_arrhenius(records, *, carrier_count, volume_A3, charge_number=1, haven_ratio=1.,
                        reference_temperature_K=298.15, density_relative_std=0., haven_relative_std=0.):
    if (not records or not all(np.isfinite(v) and v>0 for v in (carrier_count,volume_A3,charge_number,haven_ratio,reference_temperature_K))
        or not all(np.isfinite(v) and v>=0 for v in (density_relative_std,haven_relative_std))):
        raise ValueError('positive density/charge/Haven parameters required')
    groups={};identities=set()
    for row in records:
        if row.get('p2_verdict')!='PASS' or row.get('regime')!='DIFFUSIVE_FICKIAN':
            raise ValueError('stable diffusive trajectories required')
        t,d,var=(row[k] for k in ('temperature_K','diffusivity_m2_s','diffusivity_variance'))
        if not all(np.isfinite(v) and v>0 for v in (t,d,var)):raise ValueError('positive measured estimates and variances required')
        identity=(t,row['seed'])
        if identity in identities:raise ValueError('duplicate seed at temperature')
        identities.add(identity);groups.setdefault(t,[]).append((d,var))
    temps=np.array(sorted(groups))
    if len(temps)<3 or np.ptp(temps)<150:
        return {'p3_verdict':'INSUFFICIENT_TEMPERATURE_LEVER_ARM','qualification':'ABSTAIN','conductivity_S_cm':None}
    points=[]
    n=carrier_count/(volume_A3*1e-30)
    for t in temps:
        a=np.array(groups[t]);w=1/a[:,1];d=float(np.sum(w*a[:,0])/w.sum())
        variance=max(float(1/w.sum()),float(np.var(a[:,0],ddof=1)/len(a)) if len(a)>1 else 0.)
        sigma=n*(charge_number*E_CHARGE)**2*d/(KB_J*t*haven_ratio)/100
        points.append((d,variance,sigma))
    points=np.array(points); x=1/(KB_EV*temps); y=np.log(points[:,2]*temps)
    variances=points[:,1]/points[:,0]**2;w=1/variances
    design=np.column_stack((np.ones(len(x)),x));normal=design.T@(w[:,None]*design)
    if np.linalg.cond(normal)>1e14:raise ValueError('ill-conditioned Arrhenius fit')
    covariance=np.linalg.inv(normal); coefficients=covariance@(design.T@(w*y))
    residual=y-design@coefficients;reduced=float(np.sum(w*residual**2)/(len(x)-2))
    covariance*=max(1.,reduced)
    total=float(np.sum(w*(y-np.average(y,weights=w))**2))
    r2=1-float(np.sum(w*residual**2))/total if total>1e-30 else None
    reference=np.array([1.,1/(KB_EV*reference_temperature_K)])
    log_sigma=float(reference@coefficients-np.log(reference_temperature_K))
    variance=float(reference@covariance@reference)+density_relative_std**2+haven_relative_std**2
    interval=np.exp(np.clip(log_sigma+np.array([-1,1])*1.96*np.sqrt(max(0,variance)),-745,700))
    curvature=reduced>3 or r2 is None or r2<.95
    classification=('SUPERIONIC_THRESHOLD_MET' if interval[0]>=1e-4 and not curvature
                    else 'LOW_CONDUCTIVITY_THRESHOLD_MET' if interval[1]<1e-4 else 'UNCERTAIN')
    return {'schema_version':'rhombus-arrhenius-ensemble-v1','activation_energy_ev':float(-coefficients[1]),
            'activation_energy_std_ev':float(np.sqrt(covariance[1,1])),
            'reference_temperature_K':reference_temperature_K,'extrapolated_sigma_298k_s_cm':float(np.exp(np.clip(log_sigma,-745,700))),
            'sigma_95_ci_s_cm':interval.tolist(),'arrhenius_r2':r2,'non_arrhenius_curvature_flag':curvature,
            'curvature_interpretation':'Lack of fit, not authenticated phase-transition evidence',
            'temperatures_K':temps.tolist(),'sigma_s_cm':points[:,2].tolist(),'haven_ratio_assumed':haven_ratio,
            'density_m3':n,'diagnostic_class':classification,'p3_verdict':'INDETERMINATE',
            'admission_basis':'CALLER_ASSERTED_GATE_LABELS_NOT_INDEPENDENT_TRAJECTORY_VERIFICATION',
            'interval_scope':'Conditional normal interval; fixed model/Haven convention, no extrapolation-model guarantee',
            'qualification':'ABSTAIN','conductivity_S_cm':None}
