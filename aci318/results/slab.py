from dataclasses import dataclass, field
from typing import Any, List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult


@dataclass
class SlabDesignResult:
    """
    Result object storing one-way or two-way slab design outcomes according to ACI 318 Chapter 7 / Chapter 8.
    """
    thickness: float                     # Slab thickness h (in)
    required_flexure_As: float          # Required flexural steel per unit width (in^2/ft)
    provided_flexure_As: float          # Provided steel per unit width (in^2/ft)
    suggested_bar_spacing: float        # Suggested bar spacing (in)
    bar_size: str                       # Bar size (e.g., "#4")
    temp_shrinkage_As: float            # Required temperature/shrinkage steel (in^2/ft)
    flexure: FlexureResult
    shear: ShearResult
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
    detailing: Optional[Any] = None
