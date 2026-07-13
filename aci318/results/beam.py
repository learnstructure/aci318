from dataclasses import dataclass, field
from typing import List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult
from aci318.results.torsion import TorsionResult

@dataclass
class BeamDesignResult:
    """
    Composite result object storing the design outcomes for a concrete beam member.
    """
    flexure: FlexureResult
    shear: ShearResult
    torsion: Optional[TorsionResult] = None
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
