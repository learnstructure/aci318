"""
Base classes for reinforcement detailing schemas in aci318 with zero-dependency fallback.
"""

from dataclasses import dataclass, field
from typing import List, Optional

try:
    from pydantic import Field
    from aci318.base import BaseSchemaModel

    class BarPlacement(BaseSchemaModel):
        """Describes a single reinforcing bar placement."""

        id: str = Field(description="Unique identifier for the bar placement")
        bar_size: str = Field(description="Bar designation, e.g. #8")
        count: int = Field(default=1, gt=0, description="Number of bars")
        location: str = Field(description="Location description, e.g. top, bottom, stirrup")
        spacing: Optional[float] = Field(default=None, description="Spacing in inches")
        cover: Optional[float] = Field(default=None, description="Clear cover in inches")
        notes: Optional[str] = Field(default=None, description="Extra detailing notes")

    class ReinforcementDetail(BaseSchemaModel):
        """A generic reinforcement detailing object for a member."""

        id: str = Field(description="Unique detail identifier")
        member_id: str = Field(description="Reference to the structural member or element")
        detail_type: str = Field(description="Type of detail, e.g. beam, column, footing")
        bars: List[BarPlacement] = Field(default_factory=list, description="List of reinforcing bars")
        stirrups: List[BarPlacement] = Field(default_factory=list, description="List of stirrups or ties")
        notes: Optional[str] = Field(default=None, description="Overall detailing notes")

except ImportError:
    @dataclass
    class BarPlacement:
        """Describes a single reinforcing bar placement."""
        id: str
        bar_size: str
        count: int = 1
        location: str = "bottom"
        spacing: Optional[float] = None
        cover: Optional[float] = None
        notes: Optional[str] = None

    @dataclass
    class ReinforcementDetail:
        """A generic reinforcement detailing object for a member."""
        id: str
        member_id: str
        detail_type: str = "generic"
        bars: List[BarPlacement] = field(default_factory=list)
        stirrups: List[BarPlacement] = field(default_factory=list)
        notes: Optional[str] = None
