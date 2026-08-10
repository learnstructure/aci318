"""
Physical and mathematical constants for ACI 318 structural concrete calculations.
All stress units are in ksi, dimensions in inches, forces in kips unless otherwise noted.
"""

# Steel Elastic Modulus (ksi) - ACI 318-19 §20.2.2.2
ES_DEFAULT: float = 29000.0

# Concrete Maximum Compressive Strain - ACI 318-19 §22.2.2.1
EPSILON_CU: float = 0.003

# Unit Weight of Normal Weight Concrete (kcf = kips/ft^3) - ACI 318-19 §19.2.3
WC_NORMAL: float = 0.145  # kcf (145 pcf)

# Default Clear Cover (inches) - ACI 318-19 Table 20.5.1.3.1
COVER_BEAM_DEFAULT: float = 1.5
COVER_COLUMN_DEFAULT: float = 1.5
COVER_SLAB_INTERIOR_DEFAULT: float = 0.75
COVER_FOOTING_CAST_AGAINST_EARTH: float = 3.0

# Standard ASTM Bar Designations
ALL_BAR_SIZES: tuple[str, ...] = (
    "#3", "#4", "#5", "#6", "#7", "#8", "#9", "#10", "#11", "#14", "#18"
)
