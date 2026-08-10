"""Base classes for reinforcement detailing schemas in aci318."""

from typing import List, Optional
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
