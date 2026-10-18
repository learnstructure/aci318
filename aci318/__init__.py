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
    CombinedFootingDetail,
    IsolatedFootingDetail,
    ReinforcementDetail,
    SlabDetail,
    StripFootingDetail,
    create_beam_detail,
    create_beam_detail_from_design_result,
    create_column_detail,
    create_combined_footing_detail,
    create_isolated_footing_detail,
    create_slab_detail,
    create_strip_footing_detail,
)
from .foundations.isolated import IsolatedFooting, IsolatedFootingDesignResult
from .foundations.strip import StripFooting, StripFootingDesignResult
from .foundations.combined import CombinedFooting, CombinedFootingDesignResult
from .foundations.pilecap import PileCap, PileCapDesignResult
from .foundations.raft import RaftFoundation, RaftFoundationDesignResult
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
from .serviceability.deflection import (
    BeamDeflectionResult,
    calculate_beam_deflection,
    calculate_cracked_inertia,
    calculate_cracking_moment,
    calculate_effective_inertia,
    calculate_long_term_factor,
)
from .serviceability.crack import (
    CrackControlResult,
    check_crack_control_spacing,
    verify_crack_control,
)
from .strength import AxialStrength, FlexureStrength, InteractionStrength, ShearStrength, TorsionStrength
from .strength.development.development_length_engine import calculate_development_length
from .strength.development.splice_engine import design_splice
from .utils import constants, units
from .adapters import design_from_core

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
    "BeamDeflectionResult",
    "CircularSection",
    "Column",
    "ColumnDetail",
    "CombinedFooting",
    "CombinedFootingDesignResult",
    "CombinedFootingDetail",
    "Concrete",
    "CrackControlResult",
    "FlexureStrength",
    "InteractionStrength",
    "IsolatedFooting",
    "IsolatedFootingDesignResult",
    "IsolatedFootingDetail",
    "LoadEffects",
    "MarkdownReport",
    "OptimalBeamResult",
    "PileCap",
    "PileCapDesignResult",
    "RaftFoundation",
    "RaftFoundationDesignResult",
    "Rebar",
    "RebarLayer",
    "RectangleSection",
    "ReinforcementDetail",
    "ShearStrength",
    "Slab",
    "SlabDetail",
    "Steel",
    "StripFooting",
    "StripFootingDesignResult",
    "StripFootingDetail",
    "TBeamSection",
    "TorsionStrength",
    "Wall",
    "calculate_beam_deflection",
    "calculate_cracked_inertia",
    "calculate_cracking_moment",
    "calculate_development_length",
    "calculate_effective_inertia",
    "calculate_long_term_factor",
    "check_crack_control_spacing",
    "constants",
    "create_beam_detail",
    "create_beam_detail_from_design_result",
    "create_column_detail",
    "create_combined_footing_detail",
    "create_isolated_footing_detail",
    "create_slab_detail",
    "create_strip_footing_detail",
    "design_from_core",
    "design_splice",
    "units",
    "verify_crack_control",
]
