from dataclasses import dataclass, field
from typing import List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult
from aci318.results.torsion import TorsionResult

@dataclass
class BeamCheckResult:
    """
    Composite result object storing the check/verification outcomes for a concrete beam member.
    """
    flexure: FlexureResult
    shear: ShearResult
    torsion: Optional[TorsionResult] = None
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)


# Alias for backward compatibility
BeamDesignResultOld = BeamCheckResult


@dataclass
class BeamDesignResult:
    """
    Result object storing the structural design outcomes for a concrete beam member,
    including required steel areas and suggested physical bar layouts.
    """
    required_flexure_As: float          # Required tension steel area (in^2)
    suggested_bars: str                 # Suggested bar layout (e.g., "3 #8")
    provided_flexure_As: float          # Provided tension steel area (in^2)
    required_shear_spacing: float       # Required/recommended stirrup spacing (in)
    stirrup_bar_size: str               # Stirrup bar size used for design (e.g., "#3")
    stirrup_legs: int                   # Stirrup legs used for design (e.g., 2)
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
