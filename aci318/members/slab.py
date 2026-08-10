import math
from typing import Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import BAR_DATABASE, Rebar
from aci318.detailing.slab import create_slab_detail
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.slab import SlabDesignResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.validators.loads import validate_load_effects


class Slab:
    """
    Coordinates one-way and two-way reinforced concrete slab design according to ACI 318-19 Chapter 7.
    """

    def __init__(
        self,
        thickness: float,
        concrete: Concrete,
        code: DesignCode,
        member_id: str = "slab-01",
        cover: float = 0.75,
        bar_size: str = "#4",
        fy: float = 60.0,
    ) -> None:
        self.thickness = thickness
        self.concrete = concrete
        self.code = code
        self.member_id = member_id
        self.cover = cover
        self.bar_size = bar_size
        self.fy = fy

    def design(self, loads: LoadEffects) -> SlabDesignResult:
        """
        Design one-way slab per foot width (12-inch design strip) according to ACI 318-19 §7.5 & §7.6.
        
        Args:
            loads: LoadEffects instance per foot strip width (Mu in kip-in/ft, Vu in kip/ft).
            
        Returns:
            SlabDesignResult dataclass.
        """
        validate_load_effects(loads)

        strip_width = 12.0  # 12 inches design strip
        rebar = Rebar(bar_size=self.bar_size)
        effective_depth = self.thickness - self.cover - (rebar.diameter / 2.0)

        # Minimum temperature and shrinkage reinforcement (ACI 318-19 §24.4.3.2)
        # As_ts = 0.0018 * b * h for Grade 60 steel
        rho_ts = 0.0018 if self.fy >= 60.0 else 0.0020
        as_temp_shrinkage = rho_ts * strip_width * self.thickness  # in^2/ft

        # Minimum flexural steel ratio
        rho_min = self.code.get_minimum_steel_ratio(self.concrete.fc, self.fy)
        as_flexure_min = max(rho_min * strip_width * effective_depth, as_temp_shrinkage)

        # Iterative design for required flexural reinforcement
        b = strip_width
        h = self.thickness
        Mu = loads.Mu
        Vu = abs(loads.Vu)

        # Select spacing for candidate bar size
        ab = rebar.area
        # As_provided = (12.0 / spacing) * ab => spacing = 12.0 * ab / As
        target_As = as_flexure_min

        # Trial calculation for required As from Mu
        fc = self.concrete.fc
        beta_1 = self.code.get_beta_1(fc)
        phi_flexure = 0.90

        if Mu > 0.0:
            # Mu = phi * As * fy * (d - a/2)
            # a = As * fy / (0.85 * fc * b)
            # Quadratic for As
            A_coef = (phi_flexure * (self.fy ** 2)) / (1.7 * fc * b)
            B_coef = -phi_flexure * self.fy * effective_depth
            C_coef = Mu
            disc = B_coef ** 2 - 4.0 * A_coef * C_coef

            if disc >= 0.0:
                as_req_mu = (-B_coef - math.sqrt(disc)) / (2.0 * A_coef)
                target_As = max(target_As, as_req_mu)

        # Determine bar spacing (rounded down to nearest 0.5 inch)
        raw_spacing = (12.0 * ab) / max(target_As, 0.01)
        # Maximum spacing limit (ACI 318-19 §7.7.2.3: min(3*h, 18 in))
        max_spacing = min(3.0 * h, 18.0)
        final_spacing = min(math.floor(raw_spacing * 2.0) / 2.0, max_spacing)
        final_spacing = max(final_spacing, 3.0)

        provided_As = (12.0 / final_spacing) * ab

        # Create 12-inch strip section for verification
        strip_section = RectangleSection(b=strip_width, h=self.thickness, concrete=self.concrete)
        strip_section.add_rebar_layer(
            area=provided_As,
            depth=effective_depth,
            steel=Steel(fy=self.fy),
            num_bars=int(round(12.0 / final_spacing)),
            bar_size=self.bar_size,
        )

        flexure_res = FlexureStrength(strip_section, self.code).check(loads)
        shear_res = ShearStrength(strip_section, self.code).check(loads)

        status = "Passed"
        messages = []
        if flexure_res.status == "Failed" or shear_res.status == "Failed":
            status = "Failed"
        elif flexure_res.status == "Warning" or shear_res.status == "Warning":
            status = "Warning"

        messages.extend(flexure_res.messages)
        messages.extend(shear_res.messages)

        from aci318.detailing.base import BarPlacement

        bars = [
            BarPlacement(
                id=f"{self.member_id}-bottom-1",
                bar_size=self.bar_size,
                count=int(round(12.0 / final_spacing)),
                location="bottom",
                spacing=final_spacing,
                cover=self.cover,
            )
        ]
        detailing_obj = create_slab_detail(member_id=self.member_id, bars=bars)

        return SlabDesignResult(
            thickness=self.thickness,
            required_flexure_As=target_As,
            provided_flexure_As=provided_As,
            suggested_bar_spacing=final_spacing,
            bar_size=self.bar_size,
            temp_shrinkage_As=as_temp_shrinkage,
            flexure=flexure_res,
            shear=shear_res,
            status=status,
            messages=messages,
            detailing=detailing_obj,
        )
