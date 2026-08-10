from dataclasses import dataclass, field
from typing import List, Tuple
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel

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

    def __post_init__(self) -> None:
        if self.b <= 0:
            raise ValueError("Section width b must be positive.")
        if self.h <= 0:
            raise ValueError("Section height h must be positive.")

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
