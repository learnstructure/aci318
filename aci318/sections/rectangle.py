from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel

# Clear cover to the transverse reinforcement (in) of a section that names none: ACI 318-25 Table 20.5.1.3.1, beams
# and columns not exposed to weather or in contact with ground. A design takes its section's own cover.
DEFAULT_COVER = 1.5

@dataclass
class RebarLayer:
    """
    Represents a layer of reinforcing steel bars in a section.
    """
    area: float                # Total steel area in this layer (in^2)
    depth: float               # Depth from extreme compression fiber to centroid of this layer (in)
    steel: Steel               # Steel material object for this layer
    num_bars: int = None       # Number of bars in this layer (optional)
    bar_size: str = None       # Size designation of the bars (optional)

@dataclass
class RectangleSection:
    """
    Represents a rectangular reinforced concrete section.
    All dimensions are in inches, areas in square inches.
    """
    b: float                   # Width of the section (in)
    h: float                   # Height of the section (in)
    concrete: Concrete         # Concrete material
    layers: List[RebarLayer] = field(default_factory=list) # List of longitudinal reinforcement layers
    # (bars_per_b_face, bars_per_h_face, bar_size, cover, tie_bar_size, steel) set by setup_perimeter_bar_pattern
    bar_pattern: Optional[tuple] = field(default=None, repr=False)
    cover: float = DEFAULT_COVER  # Clear cover to the transverse reinforcement (in)

    def __post_init__(self) -> None:
        if self.b <= 0:
            raise ValueError("Section width b must be positive.")
        if self.h <= 0:
            raise ValueError("Section height h must be positive.")
        if self.cover <= 0:
            raise ValueError("Clear cover must be positive.")

    @property
    def gross_area(self) -> float:
        """
        Get gross cross-sectional area (Ag) in in^2.
        """
        return self.b * self.h

    @property
    def gross_inertia(self) -> float:
        """
        Get gross moment of inertia (Ig) about centroidal axis in in^4.
        """
        return (self.b * (self.h ** 3)) / 12.0

    @property
    def centroid(self) -> float:
        """
        Get distance from extreme compression fiber to geometric centroid of concrete section (in).
        """
        return self.h / 2.0

    @property
    def tension_steel(self) -> Tuple[float, float]:
        """
        Helper property that returns (As, d) for the primary tension reinforcement.
        Assumes tension reinforcement is in the bottom half of the section (depth > h/2).
        Returns:
            Tuple[float, float]: (Total tension steel area As, centroidal depth d).
        """
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

    @property
    def compression_steel(self) -> Tuple[float, float]:
        """
        Helper property that returns (As_prime, d_prime) for primary compression reinforcement.
        Assumes compression reinforcement is in the top half of the section (depth <= h/2).
        Returns:
            Tuple[float, float]: (Total compression steel area As', centroidal depth d').
        """
        comp_layers = [lyr for lyr in self.layers if lyr.depth <= self.centroid]
        if not comp_layers:
            return 0.0, 0.0
            
        total_area = sum(lyr.area for lyr in comp_layers)
        if total_area == 0.0:
            return 0.0, 0.0
            
        weighted_depth = sum(lyr.depth * lyr.area for lyr in comp_layers) / total_area
        return total_area, weighted_depth

    def add_rebar_layer(
        self,
        area: float = None,
        depth: float = None,
        steel: Steel = None,
        num_bars: int = None,
        bar_size: str = None,
        rebar: 'Rebar' = None
    ) -> None:
        """
        Add a layer of reinforcement to the section.
        Can be specified by:
        1. area directly (e.g., area=2.37)
        2. a Rebar instance and num_bars (e.g., rebar=Rebar("#8"), num_bars=3)
        3. both num_bars and bar_size (e.g., num_bars=3, bar_size="#8")
        """
        if depth is None:
            raise ValueError("Rebar depth must be specified.")
        if steel is None:
            raise ValueError("Steel material must be specified.")

        if area is None:
            if rebar is not None:
                if num_bars is None:
                    num_bars = 1
                if num_bars <= 0:
                    raise ValueError("Number of bars must be positive.")
                area = num_bars * rebar.area
                bar_size = rebar.bar_size
            elif num_bars is not None and bar_size is not None:
                if num_bars <= 0:
                    raise ValueError("Number of bars must be positive.")
                from aci318.database.bars import Rebar
                r = Rebar(bar_size=bar_size)
                area = num_bars * r.area
            else:
                raise ValueError("Must provide 'area', a 'rebar' with optional 'num_bars', or both 'num_bars' and 'bar_size'.")

        if area <= 0:
            raise ValueError("Rebar area must be positive.")
        if not (0 <= depth <= self.h):
            raise ValueError(f"Rebar depth must be within section height 0 and {self.h}.")

        self.layers.append(RebarLayer(area, depth, steel, num_bars, bar_size))

    def setup_perimeter_bar_pattern(
        self,
        num_bars: int,
        bar_size: str,
        cover: Optional[float] = None,
        tie_bar_size: str = "#3",
        steel: Steel = None,
    ) -> None:
        """
        Arrange ``num_bars`` equal bars around the perimeter of a tied column (ACI 318 §10.7.3.1:
        at least 4 bars in a rectangular arrangement).

        Four corner bars are placed first; the remaining bars are split between the faces in
        proportion to their lengths, symmetric about both axes. Layers are stored by depth for
        bending about the axis parallel to ``b`` (section depth ``h``).

        Args:
            num_bars: Total number of longitudinal bars (even, >= 4).
            bar_size: Bar size designation (e.g. '#8').
            cover: Clear cover to the ties in inches (default: the section's ``cover``).
            tie_bar_size: Tie bar size designation.
            steel: Steel material object.
        """
        if steel is None:
            raise ValueError("Steel material must be specified.")
        n_b, n_h = self.perimeter_bar_counts(num_bars)
        self._place_perimeter_bars(n_b, n_h, bar_size, self.cover if cover is None else cover, tie_bar_size, steel)

    def perimeter_bar_counts(self, num_bars: int) -> Tuple[int, int]:
        """
        Bars on each b-face and on each h-face (corners included) for ``num_bars`` perimeter bars.

        Four corner bars come first; the intermediate bars are split between the faces in proportion
        to their lengths, symmetric about both axes.
        """
        if num_bars < 4 or num_bars % 2 != 0:
            raise ValueError("A rectangular tied column needs an even number of bars, at least 4.")
        intermediate = (num_bars - 4) // 2  # intermediate bars on one b-face plus one h-face
        on_b = int(round(intermediate * self.b / (self.b + self.h)))
        return 2 + on_b, 2 + (intermediate - on_b)

    def _place_perimeter_bars(
        self, n_b: int, n_h: int, bar_size: str, cover: float, tie_bar_size: str, steel: Steel
    ) -> None:
        """Place ``n_b`` bars on each b-face and ``n_h`` bars on each h-face (corners shared)."""
        from aci318.database.bars import Rebar

        bar = Rebar(bar_size=bar_size)
        edge = cover + Rebar(bar_size=tie_bar_size).diameter + bar.diameter / 2.0
        if self.h - 2.0 * edge <= 0.0 or self.b - 2.0 * edge <= 0.0:
            raise ValueError("Section is too small for the cover, tie, and bar size.")

        self.layers = [
            RebarLayer(area=n_b * bar.area, depth=edge, steel=steel, num_bars=n_b, bar_size=bar_size)
        ]
        spacing = (self.h - 2.0 * edge) / (n_h - 1)
        for i in range(1, n_h - 1):
            self.layers.append(
                RebarLayer(area=2 * bar.area, depth=edge + i * spacing, steel=steel, num_bars=2, bar_size=bar_size)
            )
        self.layers.append(
            RebarLayer(area=n_b * bar.area, depth=self.h - edge, steel=steel, num_bars=n_b, bar_size=bar_size)
        )
        self.bar_pattern = (n_b, n_h, bar_size, cover, tie_bar_size, steel)

    def get_weak_axis_section(self) -> 'RectangleSection':
        """
        Return an equivalent RectangleSection oriented for bending about the weak axis (Y-axis).
        Swaps width and height (b_new = h, h_new = b) and maps perimeter rebar layers accordingly.
        """
        if self.bar_pattern is not None:
            n_b, n_h, bar_size, cover, tie_bar_size, steel = self.bar_pattern
            weak = RectangleSection(b=self.h, h=self.b, concrete=self.concrete, cover=self.cover)
            weak._place_perimeter_bars(n_h, n_b, bar_size, cover, tie_bar_size, steel)
            return weak

        if not self.layers:
            return RectangleSection(b=self.h, h=self.b, concrete=self.concrete, layers=[], cover=self.cover)

        # Estimate effective cover from existing rebar layers
        covers = [min(lyr.depth, self.h - lyr.depth) for lyr in self.layers if lyr.depth > 0]
        cover = min(covers) if covers else 1.5

        total_area = sum(lyr.area for lyr in self.layers)
        steel = self.layers[0].steel

        # In weak axis, section depth is b. Outer tension and compression layers placed at cover and b - cover
        d1 = max(0.5, cover)
        d2 = max(d1 + 0.5, self.b - cover)

        weak_layers = [
            RebarLayer(area=total_area / 2.0, depth=d1, steel=steel),
            RebarLayer(area=total_area / 2.0, depth=d2, steel=steel),
        ]
        return RectangleSection(b=self.h, h=self.b, concrete=self.concrete, layers=weak_layers, cover=self.cover)

