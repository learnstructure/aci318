from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class PMInteractionResult:
    """
    Result object storing outputs from P-M interaction diagram engines.
    """
    points: List[Tuple[float, float]] # List of (Nominal Moment Mn, Nominal Axial Pn) points (kip-in, kip)
    phi_points: List[Tuple[float, float]] # List of (Design Moment phi*Mn, Design Axial phi*Pn) points (kip-in, kip)
    status: str
    messages: List[str] = field(default_factory=list)
