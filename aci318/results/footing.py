"""
Foundation design results for isolated, strip, and combined footings according to ACI 318-19.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult


@dataclass
class IsolatedFootingDesignResult:
    """
    Design results for isolated spread footing according to ACI 318-19 Chapters 13 & 22.
    """
    length: float                        # Footing length L (ft)
    width: float                         # Footing width B (ft)
    thickness: float                     # Footing thickness H (in)
    max_bearing_pressure: float          # Maximum soil bearing pressure q_max (ksf)
    allowable_bearing_capacity: float    # Allowable soil capacity q_allow (ksf)
    one_way_shear: ShearResult           # One-way beam shear evaluation
    punching_shear: ShearResult          # Two-way punching shear evaluation
    flexure_x: FlexureResult             # Flexural check along X direction
    flexure_y: FlexureResult             # Flexural check along Y direction
    required_As_x: float                 # Required steel area in X direction (in^2)
    required_As_y: float                 # Required steel area in Y direction (in^2)
    status: str = "Passed"               # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list)
    detailing: Optional[Any] = None


@dataclass
class StripFootingDesignResult:
    """
    Design results for continuous strip / wall footing according to ACI 318-19 Chapters 13 & 22.
    """
    width: float                           # Footing width B in feet
    thickness: float                       # Footing thickness H in inches
    wall_thickness: float                  # Wall thickness tw in inches
    max_bearing_pressure: float            # Peak soil pressure qmax in ksf
    allowable_bearing_capacity: float      # Allowable soil pressure in ksf
    one_way_shear: ShearResult             # One-way shear evaluation
    flexure: FlexureResult                 # Transverse flexural check
    transverse_bar_size: str               # Transverse bar designation
    transverse_bar_spacing: float          # Transverse bar spacing in inches
    longitudinal_bar_size: str             # Longitudinal bar designation
    longitudinal_bar_count: int            # Number of continuous longitudinal bars
    status: str = "Passed"                 # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list)
    detailing: Optional[Any] = None


@dataclass
class CombinedFootingDesignResult:
    """
    Design results for two-column combined rectangular footing according to ACI 318-19 Chapters 13 & 22.
    """
    length: float                      # Footing length L in feet
    width: float                       # Footing width B in feet
    thickness: float                   # Footing thickness H in inches
    soil_pressure: float               # Soil bearing pressure in ksf
    allowable_pressure: float          # Allowable soil pressure in ksf
    punching_shear_col1: ShearResult   # Punching shear at Column 1
    punching_shear_col2: ShearResult   # Punching shear at Column 2
    one_way_shear: ShearResult         # Critical one-way shear
    longitudinal_flexure: FlexureResult# Longitudinal bending between columns
    top_steel_bars: str                # Suggested top longitudinal reinforcement
    bottom_steel_bars: str             # Suggested bottom longitudinal reinforcement
    status: str = "Passed"             # "Passed", "Warning", or "Failed"
    messages: List[str] = field(default_factory=list)
    detailing: Optional[Any] = None


__all__ = [
    "IsolatedFootingDesignResult",
    "StripFootingDesignResult",
    "CombinedFootingDesignResult",
]
