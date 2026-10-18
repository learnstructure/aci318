"""
Continuous strip / wall footing design coordinator according to ACI 318-19 Chapters 13 & 22.
Evaluates soil bearing pressure, one-way shear at distance d from wall face,
and transverse flexural reinforcement per linear foot of wall.
"""

from __future__ import annotations

import math
from typing import List, Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import BAR_DATABASE, Rebar
from aci318.detailing.base import BarPlacement
from aci318.detailing.footing import create_strip_footing_detail
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.flexure import FlexureResult
from aci318.results.footing import StripFootingDesignResult
from aci318.results.shear import ShearResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.validators.loads import validate_load_effects

__all__ = [
    "StripFooting",
    "StripFootingDesignResult",
]


class StripFooting:
    """
    Continuous strip / wall footing design coordinator according to ACI 318-19.
    All calculations performed per linear foot of wall length.
    """

    def __init__(
        self,
        width: float,                     # Footing width B in feet
        thickness: float,                 # Footing thickness H in inches
        wall_thickness: float,            # Supported concrete or masonry wall thickness in inches
        concrete: Concrete,
        steel: Steel,
        code: DesignCode,
        allowable_q: float = 4.0,         # Allowable soil bearing capacity in ksf
        cover: float = 3.0,               # Clear cover in inches (cast against soil)
        transverse_bar_size: str = "#5",
        longitudinal_bar_size: str = "#4",
        member_id: str = "strip-ftg-01",
    ) -> None:
        self.width = width
        self.thickness = thickness
        self.wall_thickness = wall_thickness
        self.concrete = concrete
        self.steel = steel
        self.code = code
        self.allowable_q = allowable_q
        self.cover = cover
        self.transverse_bar_size = transverse_bar_size
        self.longitudinal_bar_size = longitudinal_bar_size
        self.member_id = member_id

    def design(self, loads: LoadEffects) -> StripFootingDesignResult:
        """
        Design continuous wall footing per linear foot of wall (12-inch design strip).
        
        Args:
            loads: LoadEffects object containing Pu (kip/ft) and optional Mu (kip-ft/ft).
            
        Returns:
            StripFootingDesignResult dataclass.
        """
        validate_load_effects(loads)

        pu_per_ft = max(loads.Pu, 0.0)
        # LoadEffects specifies moment in kip-in (or kip-in/ft). Convert to kip-ft/ft.
        mu_per_ft = abs(loads.Mu) / 12.0

        # Soil bearing pressure per linear foot: Area = B * 1.0 ft
        b_ft = self.width
        area_per_ft = b_ft * 1.0

        status = "Passed"
        messages = []

        q_avg = pu_per_ft / max(area_per_ft, 0.01) if area_per_ft > 0 else 0.0
        if pu_per_ft > 0.0 and b_ft > 0.0:
            e = mu_per_ft / pu_per_ft
            if e <= b_ft / 6.0:
                q_max = q_avg * (1.0 + 6.0 * e / b_ft)
            elif e < b_ft / 2.0:
                # Triangular bearing with lift-off
                q_max = (2.0 * pu_per_ft) / (3.0 * max(b_ft / 2.0 - e, 0.01))
            else:
                q_max = 999.0
                status = "Failed"
                messages.append(f"Strip footing is unstable against overturning (eccentricity e={e:.2f} ft >= B/2={b_ft/2.0:.2f} ft).")
        else:
            q_max = 0.0

        if q_max > self.allowable_q:
            if status != "Failed":
                status = "Warning"
            messages.append(
                f"Maximum soil pressure ({q_max:.2f} ksf) exceeds allowable bearing capacity ({self.allowable_q:.2f} ksf)."
            )

        t_rebar = Rebar(bar_size=self.transverse_bar_size)
        d = max(self.thickness - self.cover - (t_rebar.diameter / 2.0), 1.0)

        # Factored net soil pressure in psi
        qu_ksf = max(q_max, 0.01)
        qu_psi = (qu_ksf * 1000.0) / 144.0

        # One-way shear at distance d from wall face
        cant_in = max(((self.width * 12.0) - self.wall_thickness) / 2.0, 0.0)
        l_shear_in = max(cant_in - d, 0.0)

        strip_b_in = 12.0  # 1-ft design strip
        vu_lb = qu_psi * strip_b_in * l_shear_in
        vu_kip = vu_lb / 1000.0

        lambda_val = self.code.get_lambda_(self.concrete)
        phi_v = self.code.get_phi_shear()

        # Size effect and Vc for members without shear reinforcement (ACI 318-19 Table 22.5.5.1)
        rho_est = max(0.0018 * self.thickness / d, 0.0015)
        vc_kip = self.code.get_vc(
            f_c=self.concrete.fc,
            b_w=strip_b_in,
            d=d,
            N_u=0.0,
            A_g=strip_b_in * self.thickness,
            A_v=0.0,
            A_v_min=0.0,
            lambda_val=lambda_val,
            rho_w=rho_est,
        )
        phi_vc = phi_v * vc_kip
        dcr_shear = vu_kip / phi_vc if phi_vc > 0 else 0.0

        shear_res = ShearResult(
            vn_concrete=vc_kip,
            vn_steel=0.0,
            phi_vn=phi_vc,
            required_spacing=0.0,
            status="Passed" if dcr_shear <= 1.0 else "Failed",
            messages=[] if dcr_shear <= 1.0 else [f"One-way shear DCR {dcr_shear:.2f} > 1.0."],
            demand_capacity_ratio=dcr_shear,
        )

        # Transverse flexural moment at wall face
        mu_kipin = (qu_psi * strip_b_in * (cant_in ** 2) / 2.0) / 1000.0

        # Minimum temperature/shrinkage reinforcement (ACI 318-19 §24.4.3.2)
        as_min_per_ft = 0.0018 * strip_b_in * self.thickness

        a_approx = 0.85
        fy = self.steel.fy
        as_req_per_ft = max(
            mu_kipin / max(0.90 * fy * (d - a_approx / 2.0), 1.0),
            as_min_per_ft,
        )

        # Transverse bar spacing
        ab_t = t_rebar.area
        raw_spacing = (12.0 * ab_t) / max(as_req_per_ft, 0.01)
        max_spacing = min(3.0 * self.thickness, 18.0)
        trans_spacing = min(math.floor(raw_spacing * 2.0) / 2.0, max_spacing)
        trans_spacing = max(trans_spacing, 4.0)

        as_prov_per_ft = (12.0 / trans_spacing) * ab_t

        sec_strip = RectangleSection(b=strip_b_in, h=self.thickness, concrete=self.concrete)
        sec_strip.add_rebar_layer(
            area=as_prov_per_ft,
            depth=d,
            steel=self.steel,
            num_bars=int(round(12.0 / trans_spacing)),
            bar_size=self.transverse_bar_size,
        )
        flex_res = FlexureStrength(sec_strip, self.code).check(LoadEffects(Mu=mu_kipin))

        # Longitudinal temperature/shrinkage reinforcement across entire footing width
        total_b_in = self.width * 12.0
        as_long_total = 0.0018 * total_b_in * self.thickness
        l_rebar = Rebar(bar_size=self.longitudinal_bar_size)
        num_long_bars = max(int(math.ceil(as_long_total / l_rebar.area)), 2)

        if dcr_shear > 1.0 or flex_res.demand_capacity_ratio > 1.0:
            status = "Failed"

        bars_detail = [
            BarPlacement(
                id=f"{self.member_id}-transverse",
                bar_size=self.transverse_bar_size,
                count=int(round(12.0 / trans_spacing)),
                location="bottom_transverse",
                spacing=trans_spacing,
                cover=self.cover,
            ),
            BarPlacement(
                id=f"{self.member_id}-longitudinal",
                bar_size=self.longitudinal_bar_size,
                count=num_long_bars,
                location="bottom_longitudinal",
                cover=self.cover + t_rebar.diameter,
            ),
        ]
        detail_obj = create_strip_footing_detail(
            member_id=self.member_id,
            bars=bars_detail,
        )

        return StripFootingDesignResult(
            width=self.width,
            thickness=self.thickness,
            wall_thickness=self.wall_thickness,
            max_bearing_pressure=round(q_max, 2),
            allowable_bearing_capacity=self.allowable_q,
            one_way_shear=shear_res,
            flexure=flex_res,
            transverse_bar_size=self.transverse_bar_size,
            transverse_bar_spacing=trans_spacing,
            longitudinal_bar_size=self.longitudinal_bar_size,
            longitudinal_bar_count=num_long_bars,
            status=status,
            messages=messages + flex_res.messages,
            detailing=detail_obj,
        )
