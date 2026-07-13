"""
Standard reinforcing bar database (US customary sizes).
"""
from dataclasses import dataclass

@dataclass(frozen=True)
def RebarInfo:
    bar_size: str             # e.g., "#8"
    diameter: float           # Nominal diameter (in)
    area: float               # Nominal cross-sectional area (in^2)
    weight: float             # Nominal weight per unit length (lb/ft)

# Standard ASTM bar sizes
BAR_DATABASE = {
    "#3": {"diameter": 0.375, "area": 0.11, "weight": 0.376},
    "#4": {"diameter": 0.500, "area": 0.20, "weight": 0.668},
    "#5": {"diameter": 0.625, "area": 0.31, "weight": 1.043},
    "#6": {"diameter": 0.750, "area": 0.44, "weight": 1.502},
    "#7": {"diameter": 0.875, "area": 0.60, "weight": 2.044},
    "#8": {"diameter": 1.000, "area": 0.79, "weight": 2.670},
    "#9": {"diameter": 1.128, "area": 1.00, "weight": 3.400},
    "#10": {"diameter": 1.270, "area": 1.27, "weight": 4.303},
    "#11": {"diameter": 1.410, "area": 1.56, "weight": 5.313},
    "#14": {"diameter": 1.693, "area": 2.25, "weight": 7.650},
    "#18": {"diameter": 2.257, "area": 4.00, "weight": 13.600},
}


def get_bar_area(bar_size: str) -> float:
    """Get the nominal cross-sectional area (in^2) of a standard bar size."""
    if bar_size not in BAR_DATABASE:
        raise ValueError(f"Unknown bar size: {bar_size}")
    return BAR_DATABASE[bar_size]["area"]


def get_bar_diameter(bar_size: str) -> float:
    """Get the nominal diameter (in) of a standard bar size."""
    if bar_size not in BAR_DATABASE:
        raise ValueError(f"Unknown bar size: {bar_size}")
    return BAR_DATABASE[bar_size]["diameter"]
