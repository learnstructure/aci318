"""aci318 - Reinforced concrete design according to ACI 318."""

from .codes.aci318_19 import ACI318_19
from .database import BAR_DATABASE
from .detailing import (
    BarPlacement,
    BeamDetail,
    ColumnDetail,
    FootingDetail,
    ReinforcementDetail,
    SlabDetail,
    create_beam_detail,
    create_beam_detail_from_design_result,
    create_column_detail,
    create_footing_detail,
    create_slab_detail,
)
from .loads.load_effects import LoadEffects
from .materials.concrete import Concrete
from .materials.steel import Steel
from .members.beam import Beam
from .members.column import Column
from .members.slab import Slab
from .reports.text_report import BeamTextReport
from .sections.rectangle import RectangleSection
from .strength import AxialStrength, FlexureStrength, InteractionStrength, ShearStrength
from .strength.development.development_length_engine import calculate_development_length

__version__ = "0.1.0"

__all__ = [
    "ACI318_19",
    "AxialStrength",
    "BAR_DATABASE",
    "BarPlacement",
    "BeamDetail",
    "ColumnDetail",
    "FootingDetail",
    "ReinforcementDetail",
    "SlabDetail",
    "Beam",
    "BeamTextReport",
    "Column",
    "Concrete",
    "FlexureStrength",
    "InteractionStrength",
    "LoadEffects",
    "RectangleSection",
    "ShearStrength",
    "Slab",
    "Steel",
    "calculate_development_length",
]
