from dataclasses import dataclass, field
from typing import Any, List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult


@dataclass
class WallDesignResult:
    """
    Result object storing structural wall design outcomes according to ACI 318 Chapter 11.
    """
    thickness: float                     # Wall thickness t (in)
    required_vertical_As: float          # Required vertical steel area (in^2/ft)
    provided_vertical_As: float          # Provided vertical steel area (in^2/ft)
    vertical_bar_spacing: float          # Vertical bar spacing (in)
    required_horizontal_As: float        # Required horizontal steel area (in^2/ft)
    provided_horizontal_As: float        # Provided horizontal steel area (in^2/ft)
    horizontal_bar_spacing: float        # Horizontal bar spacing (in)
    bar_size: str                        # Bar size used (e.g. "#4")
    flexure: FlexureResult
    shear: ShearResult
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
    detailing: Optional[Any] = None
