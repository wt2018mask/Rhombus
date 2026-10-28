"""Research declarations, never certified family-wide material properties."""
from dataclasses import dataclass

@dataclass(frozen=True)
class DomainProfile:
    family: str
    anions: tuple
    physical_risk_flags: tuple
    supported_gates: tuple = ('STATIC_GEOMETRY_DIAGNOSTIC',)
    lindemann_host_rmsd_limit_angstrom: float = 0.5
    threshold_status: str = 'PROVISIONAL_NOT_LINDEMANN_CALIBRATED'
    qualification: str = 'ABSTAIN'

PROFILES = {
    'O_ONLY': DomainProfile('O_ONLY',('O',),('GRAIN_BOUNDARY_AND_PROCESS_SENSITIVITY_UNASSESSED',)),
    'S_ONLY': DomainProfile('S_ONLY',('S',),('HYDROLYSIS_RISK_REQUIRES_ASSESSMENT','OXIDATIVE_WINDOW_UNQUALIFIED')),
    'HALIDE': DomainProfile('HALIDE',('F','Cl','Br','I'),('VACANCY_ORDERING_UNQUALIFIED','OXIDATIVE_WINDOW_UNQUALIFIED')),
}
