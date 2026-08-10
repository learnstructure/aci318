import math
from typing import Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.wall import WallDesignResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.validators.loads import validate_load_effects


class Wall:
    """
    Coordinates structural wall design according to ACI 318-19 Chapter 11.
    """

    def __init__(
        self,
        thickness: float,
        height: float,
        length: float,
        concrete: Concrete,
        code: DesignCode,
        member_id: str = "wall-01",
        cover: float = 0.75,
        bar_size: str = "#4",
        fy: float = 60.0,
    ) -> None:
        self.thickness = thickness
        self.height = height
        self.length = length
        self.concrete = concrete
        self.code = code
        self.member_id = member_id
        self.cover = cover
        self.bar_size = bar_size
        self.fy = fy

    def design(self, loads: LoadEffects) -> WallDesignResult:
        """
        Design structural wall for axial load, flexure, and shear per foot width according to ACI 318-19 §11.6.
        
        Args:
            loads: LoadEffects object per foot of wall length.
            
        Returns:
            WallDesignResult dataclass.
        """
        validate_load_effects(loads)

        strip_width = 12.0  # 12 inches
        rebar = Rebar(bar_size=self.bar_size)

        # Minimum wall reinforcement ratios (ACI 318-19 §11.6.1)
        # Vertical reinforcement: rho_v = 0.0012 for #5 or smaller bars
        # Horizontal reinforcement: rho_h = 0.0020 for #5 or smaller bars
        rho_v_min = 0.0012 if rebar.diameter <= 0.625 else 0.0015
        rho_h_min = 0.0020 if rebar.diameter <= 0.625 else 0.0025

        as_v_min = rho_v_min * strip_width * self.thickness  # in^2/ft
        as_h_min = rho_h_min * strip_width * self.thickness  # in^2/ft

        # Maximum spacing limit (ACI 318-19 §11.7.2: min(3*t, 18 in))
        max_spacing = min(3.0 * self.thickness, 18.0)

        ab = rebar.area
        # Two layers of reinforcement if wall thickness >= 10 inches (ACI 318-19 §11.7.2.3)
        num_curtains = 2 if self.thickness >= 10.0 else 1

        v_spacing_raw = (12.0 * num_curtains * ab) / max(as_v_min, 0.01)
        v_spacing = min(math.floor(v_spacing_raw * 2.0) / 2.0, max_spacing)
        v_spacing = max(v_spacing, 4.0)
        as_v_provided = (12.0 * num_curtains * ab) / v_spacing

        h_spacing_raw = (12.0 * num_curtains * ab) / max(as_h_min, 0.01)
        h_spacing = min(math.floor(h_spacing_raw * 2.0) / 2.0, max_spacing)
        h_spacing = max(h_spacing, 4.0)
        as_h_provided = (12.0 * num_curtains * ab) / h_spacing

        effective_depth = self.thickness - self.cover - (rebar.diameter / 2.0)
        wall_section = RectangleSection(b=strip_width, h=self.thickness, concrete=self.concrete)
        wall_section.add_rebar_layer(
            area=as_v_provided,
            depth=effective_depth,
            steel=Steel(fy=self.fy),
            num_bars=int(round(12.0 / v_spacing)),
            bar_size=self.bar_size,
        )

        flexure_res = FlexureStrength(wall_section, self.code).check(loads)
        shear_res = ShearStrength(wall_section, self.code).check(loads)

        status = "Passed"
        messages = []
        if flexure_res.status == "Failed" or shear_res.status == "Failed":
            status = "Failed"
        elif flexure_res.status == "Warning" or shear_res.status == "Warning":
            status = "Warning"

        messages.extend(flexure_res.messages)
        messages.extend(shear_res.messages)

        return WallDesignResult(
            thickness=self.thickness,
            required_vertical_As=as_v_min,
            provided_vertical_As=as_v_provided,
            vertical_bar_spacing=v_spacing,
            required_horizontal_As=as_h_min,
            provided_horizontal_As=as_h_provided,
            horizontal_bar_spacing=h_spacing,
            bar_size=self.bar_size,
            flexure=flexure_res,
            shear=shear_res,
            status=status,
            messages=messages,
            detailing=None,
        )
