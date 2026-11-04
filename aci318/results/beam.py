from dataclasses import dataclass, field
from typing import Any, List, Optional
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




@dataclass
class BeamDesignResult:
    """
    Result object storing structural design outcomes for a concrete beam member.
    """
    required_flexure_As: float          # Required tension steel area (in^2)
    suggested_bars: str                 # Suggested bar layout (e.g., "3 #8")
    provided_flexure_As: float          # Provided tension steel area (in^2)
    required_shear_spacing: float       # Required stirrup spacing (in)
    stirrup_bar_size: str               # Stirrup bar size (e.g., "#3")
    stirrup_legs: int                   # Stirrup legs (e.g., 2)
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
    trial_section: Optional[Any] = None  # Non-mutating trial section with designed reinforcement
    detailing: Optional[Any] = None      # ReinforcementDetail detailing object
    flexure: Optional[FlexureResult] = None  # Flexure check of the selected (or strongest fitting) layout
    shear: Optional[ShearResult] = None      # Shear check with designed stirrups, or the Vs,max section limit
    torsion: Optional[TorsionResult] = None  # Torsion check with the provided stirrups (None if Tu <= phi*Tth)
    # ACI 318 §9.3.3.1: required tension-controlled strain / provided net tensile strain (> 1 fails)
    ductility_ratio: Optional[float] = None
