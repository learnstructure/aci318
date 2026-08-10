from dataclasses import dataclass, field
from typing import List

@dataclass
class ShearResult:
    """
    Result object storing outputs from shear design engines.
    """
    vn_concrete: float          # Concrete nominal shear strength Vc (kip)
    vn_steel: float             # Steel stirrup nominal shear strength Vs (kip)
    phi_vn: float               # Design shear strength phi*Vn (kip)
    required_spacing: float     # Required stirrup spacing (in)
    status: str                 # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list) # Design notes/warnings
    demand_capacity_ratio: float = 0.0
