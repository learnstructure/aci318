"""
aci318 - Professional reinforced concrete design library based on ACI 318.
"""

from .codes.aci318_19 import ACI318_19
from .codes.aci318_25 import ACI318_25
from .database import BAR_DATABASE, Rebar
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
from .foundations.isolated import IsolatedFooting
from .loads.load_effects import LoadEffects
from .materials.concrete import Concrete
from .materials.steel import Steel
from .members.beam import Beam
from .members.column import Column
from .members.slab import Slab
from .members.wall import Wall
from .optimization.section_optimizer import BeamSectionOptimizer, OptimalBeamResult
from .reports.markdown_report import MarkdownReport
from .reports.text_report import BeamTextReport
from .sections.circle import CircularSection
from .sections.rectangle import RebarLayer, RectangleSection
from .sections.tbeam import TBeamSection
from .strength import AxialStrength, FlexureStrength, InteractionStrength, ShearStrength, TorsionStrength
from .strength.development.development_length_engine import calculate_development_length
from .strength.development.splice_engine import design_splice
from .utils import constants, units

__version__ = "0.2.0"

__all__ = [
    "ACI318_19",
    "ACI318_25",
    "AxialStrength",
    "BAR_DATABASE",
    "BarPlacement",
    "Beam",
    "BeamDetail",
    "BeamSectionOptimizer",
    "BeamTextReport",
    "CircularSection",
    "Column",
    "ColumnDetail",
    "Concrete",
    "FlexureStrength",
    "FootingDetail",
    "InteractionStrength",
    "IsolatedFooting",
    "LoadEffects",
    "MarkdownReport",
    "OptimalBeamResult",
    "Rebar",
    "RebarLayer",
    "RectangleSection",
    "ReinforcementDetail",
    "ShearStrength",
    "Slab",
    "SlabDetail",
    "Steel",
    "TBeamSection",
    "TorsionStrength",
    "Wall",
    "calculate_development_length",
    "constants",
    "create_beam_detail",
    "create_beam_detail_from_design_result",
    "create_column_detail",
    "create_footing_detail",
    "create_slab_detail",
    "design_splice",
    "units",
]
