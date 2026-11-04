import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import DEFAULT_COVER, RebarLayer


@dataclass
class CircularSection:
    """
    Represents a circular reinforced concrete section (columns, circular piers, piles).
    
    Attributes:
        D: Overall diameter in inches.
        concrete: Concrete material object.
        layers: List of rebar layers or circular pattern bars.
        cover: Clear cover to the transverse reinforcement in inches.
    """
    D: float
    concrete: Concrete
    layers: List[RebarLayer] = field(default_factory=list)
    cover: float = DEFAULT_COVER  # Clear cover to the transverse reinforcement (in)

    def __post_init__(self) -> None:
        if self.D <= 0.0:
            raise ValueError(f"Circular section diameter D must be positive, got {self.D} in.")
        if self.cover <= 0.0:
            raise ValueError("Clear cover must be positive.")

    @property
    def h(self) -> float:
        """Section height equal to diameter D."""
        return self.D

    @property
    def b(self) -> float:
        """Section width equal to diameter D."""
        return self.D

    @property
    def b_w(self) -> float:
        """Equivalent web width equal to diameter D."""
        return self.D

    @property
    def gross_area(self) -> float:
        """
        Get gross area (Ag) in sq inches.
        
        Equation:
            Ag = pi * D^2 / 4
        """
        return (math.pi * (self.D ** 2)) / 4.0

    @property
    def gross_inertia(self) -> float:
        """
        Get gross moment of inertia (Ig) in in^4.
        
        Equation:
            Ig = pi * D^4 / 64
        """
        return (math.pi * (self.D ** 4)) / 64.0

    @property
    def centroid(self) -> float:
        """Get distance from extreme compression fiber to geometric centroid (D / 2) in inches."""
        return self.D / 2.0

    @property
    def tension_steel(self) -> Tuple[float, float]:
        """Returns (As, d) for primary tension steel (bars past centroid)."""
        tension_layers = [lyr for lyr in self.layers if lyr.depth > self.centroid]
        if not tension_layers:
            return 0.0, 0.0

        total_area = sum(lyr.area for lyr in tension_layers)
        if total_area == 0.0:
            return 0.0, 0.0

        weighted_depth = sum(lyr.depth * lyr.area for lyr in tension_layers) / total_area
        return total_area, weighted_depth

    @property
    def d_t(self) -> float:
        """
        Get distance from extreme compression fiber to centroid of extreme tension reinforcement layer (in).
        Per ACI 318 Fig. R21.2.2a, this is used to calculate net tensile strain epsilon_t.
        """
        tension_layers = [lyr for lyr in self.layers if lyr.depth > self.centroid]
        if not tension_layers:
            return self.tension_steel[1]
        return max(lyr.depth for lyr in tension_layers)

    def setup_circular_bar_pattern(
        self,
        num_bars: int,
        bar_size: str,
        cover: Optional[float] = None,
        tie_bar_size: str = "#3",
        *,
        steel: Steel,
    ) -> None:
        """
        Arrange num_bars equally spaced around a circular core.
        
        Args:
            num_bars: Total number of longitudinal bars (minimum 6 for circular columns per ACI 318).
            bar_size: Bar size designation (e.g. '#8').
            cover: Clear cover to ties in inches (default: the section's ``cover``).
            tie_bar_size: Tie or spiral bar size designation.
            steel: Steel of the longitudinal bars (required).
        """
        from aci318.database.bars import Rebar

        if num_bars < 4:
            raise ValueError("Circular section must have at least 4 longitudinal bars.")

        bar = Rebar(bar_size=bar_size)
        tie = Rebar(bar_size=tie_bar_size)
        cover = self.cover if cover is None else cover

        r_core = (self.D / 2.0) - cover - tie.diameter - (bar.diameter / 2.0)
        if r_core <= 0.0:
            raise ValueError("Core radius is non-positive; check cover or section diameter.")

        self.layers = []
        angle_step = (2.0 * math.pi) / num_bars

        for i in range(num_bars):
            angle = i * angle_step
            d_bar = (self.D / 2.0) + r_core * math.cos(angle)
            self.layers.append(
                RebarLayer(
                    area=bar.area,
                    depth=d_bar,
                    steel=steel,
                    num_bars=1,
                    bar_size=bar_size,
                )
            )

    def get_weak_axis_section(self) -> 'CircularSection':
        """Circular sections are radially symmetric; weak-axis capacity equals strong-axis."""
        return self


