from dataclasses import dataclass, field
from typing import List

@dataclass
class FlexureResult:
    """
    Result object storing outputs from flexural design engines.
    """
    required_steel: float       # Required steel area (in^2)
    provided_steel: float       # Provided steel area (in^2)
    neutral_axis: float         # Depth to neutral axis c (in)
    steel_strain: float         # Net tensile strain in extreme steel layer (in/in)
    phi_mn: float               # Design bending strength (kip-in)
    status: str                 # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list) # Design warnings or failure logs
