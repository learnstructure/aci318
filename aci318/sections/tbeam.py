from dataclasses import dataclass, field
from typing import Any, List, Tuple
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import DEFAULT_COVER, RebarLayer
from aci318.validators.geometry import validate_flange_geometry


@dataclass
class TBeamSection:
    """
    Represents a flanged T-beam or L-beam reinforced concrete section according to ACI 318.
    
    Attributes:
        b_f: Effective flange width in inches.
        h_f: Flange thickness (slab thickness) in inches.
        b_w: Web (stem) width in inches.
        h: Total section height in inches.
        concrete: Concrete material object.
        layers: List of longitudinal reinforcement layers.
        cover: Clear cover to the transverse reinforcement in inches.
    """
    b_f: float
    h_f: float
    b_w: float
    h: float
    concrete: Concrete
    layers: List[RebarLayer] = field(default_factory=list)
    cover: float = DEFAULT_COVER

    def __post_init__(self) -> None:
        validate_flange_geometry(self.b_f, self.h_f, self.b_w, self.h)
        if self.cover <= 0:
            raise ValueError("Clear cover must be positive.")

    @property
    def b(self) -> float:
        """Compatibility property for web width b_w."""
        return self.b_w

    @property
    def gross_area(self) -> float:
        """
        Get gross cross-sectional area (Ag) in sq in.
        
        Equation:
            Ag = b_f * h_f + b_w * (h - h_f)
        """
        return self.b_f * self.h_f + self.b_w * (self.h - self.h_f)

    @property
    def centroid(self) -> float:
        """
        Get distance from top extreme compression fiber to geometric centroid of section (y_bar) in inches.
        """
        area_flange = self.b_f * self.h_f
        y_flange = self.h_f / 2.0
        area_web = self.b_w * (self.h - self.h_f)
        y_web = self.h_f + (self.h - self.h_f) / 2.0
        return (area_flange * y_flange + area_web * y_web) / self.gross_area

    @property
    def gross_inertia(self) -> float:
        """
        Get gross moment of inertia (Ig) about centroidal axis in in^4.
        """
        y_bar = self.centroid
        i_flange = (self.b_f * (self.h_f ** 3)) / 12.0 + (self.b_f * self.h_f) * ((y_bar - self.h_f / 2.0) ** 2)
        h_web = self.h - self.h_f
        y_web = self.h_f + h_web / 2.0
        i_web = (self.b_w * (h_web ** 3)) / 12.0 + (self.b_w * h_web) * ((y_bar - y_web) ** 2)
        return i_flange + i_web

    @property
    def tension_steel(self) -> Tuple[float, float]:
        """
        Returns (As, d) for primary tension reinforcement (layers below centroid).
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


    def add_rebar_layer(
        self,
        area: float = None,
        depth: float = None,
        steel: Steel = None,
        num_bars: int = None,
        bar_size: str = None,
        rebar: Any = None,
    ) -> None:
        """Add reinforcement layer to T-beam section."""
        if depth is None or steel is None:
            raise ValueError("Rebar depth and steel material must be specified.")

        if area is None:
            if rebar is not None:
                num_bars = num_bars or 1
                area = num_bars * rebar.area
                bar_size = rebar.bar_size
            elif num_bars is not None and bar_size is not None:
                from aci318.database.bars import Rebar
                r = Rebar(bar_size=bar_size)
                area = num_bars * r.area
            else:
                raise ValueError("Must provide 'area', 'rebar', or 'num_bars' and 'bar_size'.")

        self.layers.append(RebarLayer(area, depth, steel, num_bars, bar_size))
