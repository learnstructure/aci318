from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class InteractionResult:
    """Result object for uniaxial and biaxial axial-flexural interaction checks."""

    axial_ratio: float
    flexure_ratio: float
    demand_capacity_ratio: float
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
    phi_mn_x: Optional[float] = None
    phi_mn_y: Optional[float] = None
    biaxial_ratio: Optional[float] = None
    method_used: Optional[str] = None


@dataclass
class PMInteractionResult:
    """
    Result object storing outputs from P-M interaction diagram engines.
    """
    points: List[Tuple[float, float]] # List of (Nominal Moment Mn, Nominal Axial Pn) points (kip-in, kip)
    phi_points: List[Tuple[float, float]] # List of (Design Moment phi*Mn, Design Axial phi*Pn) points (kip-in, kip)
    status: str
    messages: List[str] = field(default_factory=list)
