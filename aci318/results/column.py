from dataclasses import dataclass, field
from typing import List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult

@dataclass
class ColumnDesignResult:
    """
    Composite result object storing the design outcomes for a concrete column member.
    """
    axial_flexure: FlexureResult
    shear: ShearResult
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
