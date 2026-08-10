from dataclasses import dataclass, field
from typing import Any, List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult


@dataclass
class FootingDesignResult:
    """
    Result object storing isolated footing design outcomes according to ACI 318 Chapter 13.
    """
    length: float                        # Footing length L (ft)
    width: float                         # Footing width B (ft)
    thickness: float                     # Footing thickness H (in)
    max_bearing_pressure: float          # Maximum soil bearing pressure q_max (ksf)
    allowable_bearing_capacity: float    # Allowable soil capacity q_allow (ksf)
    one_way_shear: ShearResult
    punching_shear: ShearResult
    flexure_x: FlexureResult
    flexure_y: FlexureResult
    required_As_x: float                 # Required steel area in X direction (in^2)
    required_As_y: float                 # Required steel area in Y direction (in^2)
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
    detailing: Optional[Any] = None
