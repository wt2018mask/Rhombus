"""Transport-regime qualification for Rhombus 2.0.

This namespace owns transport-regime admission and classification. It does not
own finite-temperature host stability or conductivity claims.
"""

from .admission import (
    TRANSPORT_REGIME_CAPABILITY,
    assess_transport_regime_admission,
)
from .classify import classify_transport_regime
from .extension import (
    TRANSPORT_EVIDENCE_EXTENSION_CAPABILITY,
    assess_transport_evidence_extension_admission,
)

__all__ = [
    "TRANSPORT_REGIME_CAPABILITY",
    "assess_transport_regime_admission",
    "classify_transport_regime",
    "TRANSPORT_EVIDENCE_EXTENSION_CAPABILITY",
    "assess_transport_evidence_extension_admission",
]
