from dataclasses import dataclass, field
from typing import List


@dataclass
class TorsionResult:
    """
    Result object storing outputs from torsion design engines according to ACI 318 §22.7.
    """
    tn_nominal: float                   # Nominal torsional strength Tn (kip-in)
    phi_tn: float                       # Design torsional strength phi*Tn (kip-in)
    required_transverse_steel: float     # Transverse steel At/s per leg (in^2/in)
    required_longitudinal_steel: float    # Total longitudinal steel Al (in^2)
    threshold_torsion: float = 0.0      # Threshold torsion Tth (kip-in)
    cracking_torsion: float = 0.0       # Cracking torsion Tcr (kip-in)
    status: str = "Passed"              # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list)
    demand_capacity_ratio: float = 0.0
