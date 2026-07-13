from dataclasses import dataclass, field
from typing import List

@dataclass
class TorsionResult:
    """
    Result object storing outputs from torsion design engines.
    """
    tn_nominal: float           # Nominal torsional strength Tn (kip-in)
    phi_tn: float               # Design torsional strength phi*Tn (kip-in)
    required_transverse_steel: float # Transverse reinforcement area per unit length (in^2/in)
    required_longitudinal_steel: float # Longitudinal reinforcement area (in^2)
    status: str                 # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list) # Design notes/warnings
