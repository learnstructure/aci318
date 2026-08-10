from dataclasses import dataclass, field
from typing import Any, List, Optional
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult


@dataclass
class ColumnDesignResult:
    """
    Composite result object storing design outcomes for a concrete column member according to ACI 318.
    """
    axial_flexure: FlexureResult
    shear: ShearResult
    status: str = "Passed"
    messages: List[str] = field(default_factory=list)
    pm_interaction: Optional[Any] = None
    detailing: Optional[Any] = None
