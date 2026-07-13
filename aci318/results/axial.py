from dataclasses import dataclass, field
from typing import List

@dataclass
class AxialResult:
    """
    Result object storing outputs from axial design engines.
    """
    pn_nominal: float           # Nominal axial strength (kip)
    phi_pn: float               # Design axial strength (kip)
    pn_max: float               # Maximum design axial strength including eccentricity factor (kip)
    phi_pn_max: float           # Factored maximum design axial strength (kip)
    status: str                 # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list)
