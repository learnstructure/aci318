"""
Combined rectangular footing design coordinator according to ACI 318-19 Chapters 13 & 22.
Supports two columns with axial loads P1 and P2, sizing length and width to align the
footing centroid with the resultant load, and evaluating bearing pressure, longitudinal flexure,
and punching shear at both columns.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.detailing.base import BarPlacement
from aci318.detailing.footing import create_combined_footing_detail
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.flexure import FlexureResult
from aci318.results.footing import CombinedFootingDesignResult
from aci318.results.shear import ShearResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength

__all__ = [
    "CombinedFooting",
    "CombinedFootingDesignResult",
]


class CombinedFooting:
    """
    Combined rectangular footing coordinator supporting two columns (ACI 318-19).
    """

    def __init__(
        self,
        column_spacing_ft: float,      # Center-to-center distance between columns in feet
        col1_c1: float,                # Column 1 dimension along length in inches
        col1_c2: float,                # Column 1 dimension along width in inches
        col2_c1: float,                # Column 2 dimension along length in inches
        col2_c2: float,                # Column 2 dimension along width in inches
        concrete: Concrete,
        steel: Steel,
        code: DesignCode,
        allowable_q: float = 5.0,      # Allowable soil bearing capacity in ksf
        cantilever_col1_ft: float = 1.5,# Cantilever projection past Column 1 in feet
        thickness: float = 24.0,       # Initial footing thickness in inches
        cover: float = 3.0,            # Clear cover in inches
        bar_size: str = "#8",
        member_id: str = "comb-ftg-01",
    ) -> None:
        self.column_spacing_ft = column_spacing_ft
        self.col1_c1 = col1_c1
        self.col1_c2 = col1_c2
        self.col2_c1 = col2_c1
        self.col2_c2 = col2_c2
        self.concrete = concrete
        self.steel = steel
        self.code = code
        self.allowable_q = allowable_q
        self.cantilever_col1_ft = cantilever_col1_ft
        self.thickness = thickness
        self.cover = cover
        self.bar_size = bar_size
        self.member_id = member_id

    def design(
        self,
        p1_kip: float,
        p2_kip: float,
        width_ft: Optional[float] = None,
    ) -> CombinedFootingDesignResult:
        """
        Design combined footing for column loads P1 and P2 (service/factored).
        
        Args:
            p1_kip: Axial load on Column 1 in kips.
            p2_kip: Axial load on Column 2 in kips.
            width_ft: Optional explicit footing width B in feet.
            
        Returns:
            CombinedFootingDesignResult dataclass.
        """
        p1 = max(float(p1_kip), 1.0)
        p2 = max(float(p2_kip), 1.0)
        p_total = p1 + p2

        # Resultant location from Column 1 center
        x_bar_ft = (p2 * self.column_spacing_ft) / p_total

        # Footing length to produce uniform soil bearing pressure:
        # Distance from edge 1 to centroid = cantilever_col1 + x_bar
        length_ft = 2.0 * (self.cantilever_col1_ft + x_bar_ft)
        length_ft = max(round(length_ft * 2.0) / 2.0, self.column_spacing_ft + 3.0)

        # Footing width B
        if width_ft is not None and width_ft > 0.0:
            b_ft = float(width_ft)
        else:
            b_req = p_total / (length_ft * self.allowable_q)
            b_ft = max(round(math.ceil(b_req * 2.0) / 2.0, 1), 3.0)

        area_ft2 = length_ft * b_ft
        q_actual = p_total / area_ft2

        status = "Passed"
        messages = []
        if q_actual > self.allowable_q:
            status = "Warning"
            messages.append(
                f"Soil bearing pressure {q_actual:.2f} ksf exceeds allowable {self.allowable_q:.2f} ksf."
            )

        rebar = Rebar(bar_size=self.bar_size)
        d = max(self.thickness - self.cover - rebar.diameter, 1.0)

        # Factored net uniform soil line load along footing length (kip/ft)
        wu_kip_per_ft = p_total / length_ft
        qu_ksf = p_total / area_ft2
        qu_psi = (qu_ksf * 1000.0) / 144.0

        # Two-Way Punching Shear Helper per ACI 318-19 Table 22.6.5.2
        def _punching_check(c1: float, c2: float, pu_col: float) -> ShearResult:
            b1 = c1 + d
            b2 = c2 + d
            bo = 2.0 * b1 + 2.0 * b2
            col_area_in2 = b1 * b2
            # Net downward punching shear: Column load minus relieving upward soil reaction within perimeter
            vu_punch_kip = max(pu_col - (qu_ksf * (col_area_in2 / 144.0)), 0.0)

            fc_psi = self.concrete.fc * 1000.0
            lambda_val = self.code.get_lambda_(self.concrete)
            phi_v = self.code.get_phi_shear()
            beta_c = max(c1 / max(c2, 1.0), c2 / max(c1, 1.0))
            lambda_s = min(math.sqrt(2.0 / (1.0 + d / 10.0)), 1.0)

            vc1 = (2.0 + 4.0 / beta_c) * lambda_s * lambda_val * math.sqrt(fc_psi)
            vc2 = (40.0 * d / bo + 2.0) * lambda_s * lambda_val * math.sqrt(fc_psi)
            vc3 = 4.0 * lambda_s * lambda_val * math.sqrt(fc_psi)
            vc_stress = min(vc1, vc2, vc3)

            vc_kip = (vc_stress * bo * d) / 1000.0
            phi_vc = phi_v * vc_kip
            dcr = vu_punch_kip / phi_vc if phi_vc > 0 else 0.0
            return ShearResult(
                vn_concrete=vc_kip,
                vn_steel=0.0,
                phi_vn=phi_vc,
                required_spacing=0.0,
                status="Passed" if dcr <= 1.0 else "Failed",
                messages=[] if dcr <= 1.0 else [f"Punching shear DCR {dcr:.2f} > 1.0."],
                demand_capacity_ratio=dcr,
            )

        punch_1 = _punching_check(self.col1_c1, self.col1_c2, p1)
        punch_2 = _punching_check(self.col2_c1, self.col2_c2, p2)

        # One-way shear critical sections at distance d from column faces (ACI 318-19 §13.4.2)
        b_in = b_ft * 12.0
        x1_ft = self.cantilever_col1_ft
        x2_ft = x1_ft + self.column_spacing_ft
        d_ft = d / 12.0

        # Col 1 faces:
        x1_left_face = x1_ft - (self.col1_c1 / 24.0)
        x1_right_face = x1_ft + (self.col1_c1 / 24.0)
        # Col 2 faces:
        x2_left_face = x2_ft - (self.col2_c1 / 24.0)
        x2_right_face = x2_ft + (self.col2_c1 / 24.0)

        # Potential critical shear locations
        v_candidates = []
        # Left cantilever at d from left face
        x_crit_left = x1_left_face - d_ft
        if x_crit_left > 0.0:
            v_candidates.append(abs(wu_kip_per_ft * x_crit_left))

        # Interior section right of Col 1 at d from right face
        x_crit_col1_r = x1_right_face + d_ft
        if x_crit_col1_r < x2_left_face:
            v_candidates.append(abs(wu_kip_per_ft * x_crit_col1_r - p1))

        # Interior section left of Col 2 at d from left face
        x_crit_col2_l = x2_left_face - d_ft
        if x_crit_col2_l > x1_right_face:
            v_candidates.append(abs(wu_kip_per_ft * x_crit_col2_l - p1))

        # Right cantilever at d from right face
        x_crit_right = x2_right_face + d_ft
        if x_crit_right < length_ft:
            v_candidates.append(abs(wu_kip_per_ft * (length_ft - x_crit_right)))

        vu_1way_kip = max(v_candidates) if v_candidates else max(p1, p2) * 0.4

        lambda_val = self.code.get_lambda_(self.concrete)
        phi_v = self.code.get_phi_shear()
        fc_psi = self.concrete.fc * 1000.0

        # Longitudinal negative bending between columns at zero-shear section x0 = p1 / wu (designed first to determine rho_w)
        x0_ft = p1 / wu_kip_per_ft
        mu_neg_kipft = p1 * (x0_ft - x1_ft) - (wu_kip_per_ft * (x0_ft ** 2) / 2.0)
        mu_neg_kipin = max(mu_neg_kipft * 12.0, 1.0)

        as_min_long = 0.0018 * b_in * self.thickness
        as_req_long = max(
            mu_neg_kipin / max(0.90 * self.steel.fy * (d - 1.0), 1.0),
            as_min_long,
        )

        num_top_bars = max(int(math.ceil(as_req_long / rebar.area)), 4)
        as_prov_top = num_top_bars * rebar.area

        sec_long = RectangleSection(b=b_in, h=self.thickness, concrete=self.concrete)
        sec_long.add_rebar_layer(
            area=as_prov_top,
            depth=d,
            steel=self.steel,
            num_bars=num_top_bars,
            bar_size=self.bar_size,
        )
        flex_res = FlexureStrength(sec_long, self.code).check(LoadEffects(Mu=mu_neg_kipin))

        # Concrete shear strength without shear reinforcement (ACI 318-19 Table 22.5.5.1) using designed rho_w
        rho_w_designed = as_prov_top / (b_in * d)
        vc_no_stirrup_kip = self.code.get_vc(
            f_c=self.concrete.fc,
            b_w=b_in,
            d=d,
            N_u=0.0,
            A_g=b_in * self.thickness,
            A_v=0.0,
            A_v_min=0.0,
            lambda_val=lambda_val,
            rho_w=rho_w_designed,
        )
        phi_vc_no_stirrup = phi_v * vc_no_stirrup_kip

        # Shear reinforcement design if Vu > phi*Vc
        one_way_messages = []
        if vu_1way_kip <= phi_vc_no_stirrup:
            vc_1way_kip = vc_no_stirrup_kip
            vs_kip = 0.0
            phi_vn_1way = phi_vc_no_stirrup
            s_stirrup = 0.0
            dcr_1way = vu_1way_kip / phi_vn_1way if phi_vn_1way > 0 else 0.0
            status_1way = "Passed"
        else:
            # Table 22.5.5.1 with stirrups Av >= Av_min: Vc = 2 * lambda * sqrt(f'c) * bw * d
            vc_with_stirrup_kip = (2.0 * lambda_val * math.sqrt(fc_psi) * b_in * d) / 1000.0
            phi_vc_with_stirrup = phi_v * vc_with_stirrup_kip
            vs_req_kip = max((vu_1way_kip / phi_v) - vc_with_stirrup_kip, 0.0)
            vs_max_kip = (8.0 * math.sqrt(fc_psi) * b_in * d) / 1000.0

            av_stirrup = 0.40  # 2-leg #4 stirrups
            if vs_req_kip > vs_max_kip:
                status_1way = "Failed"
                one_way_messages.append(f"Section depth inadequate for shear (Vs_req {vs_req_kip:.1f} > Vs_max {vs_max_kip:.1f} kip).")
                s_stirrup = 0.0
                vs_kip = vs_max_kip
            else:
                max_s = min(d / 2.0, 12.0)
                if vs_req_kip > 0.0:
                    calc_s = (av_stirrup * self.steel.fy * d) / vs_req_kip
                    s_stirrup = min(math.floor(calc_s * 2.0) / 2.0, max_s)
                else:
                    s_stirrup = max_s
                s_stirrup = max(s_stirrup, 3.0)
                vs_kip = (av_stirrup * self.steel.fy * d) / s_stirrup
                status_1way = "Passed"
                one_way_messages.append(f"Shear stirrups provided: 2-leg #4 @ {s_stirrup:.1f} in.")

            vc_1way_kip = vc_with_stirrup_kip
            phi_vn_1way = phi_v * (vc_1way_kip + vs_kip)
            dcr_1way = vu_1way_kip / phi_vn_1way if phi_vn_1way > 0 else 0.0

        shear_1way = ShearResult(
            vn_concrete=vc_1way_kip,
            vn_steel=vs_kip,
            phi_vn=phi_vn_1way,
            required_spacing=s_stirrup,
            status=status_1way,
            messages=one_way_messages,
            demand_capacity_ratio=dcr_1way,
        )

        # Bottom steel at cantilevers
        num_bot_bars = max(int(math.ceil(as_min_long / rebar.area)), 4)

        if punch_1.demand_capacity_ratio > 1.0 or punch_2.demand_capacity_ratio > 1.0 or dcr_1way > 1.0 or flex_res.demand_capacity_ratio > 1.0:
            status = "Failed"

        bars_detail = [
            BarPlacement(
                id=f"{self.member_id}-top-long",
                bar_size=self.bar_size,
                count=num_top_bars,
                location="top_longitudinal",
                cover=self.cover,
            ),
            BarPlacement(
                id=f"{self.member_id}-bot-long",
                bar_size=self.bar_size,
                count=num_bot_bars,
                location="bottom_longitudinal",
                cover=self.cover,
            ),
        ]
        detail_obj = create_combined_footing_detail(
            member_id=self.member_id,
            bars=bars_detail,
        )

        # Filter out beam minimum warning if As >= 0.0018 * b * h (ACI 318-19 §13.3.2.1)
        flex_clean_messages = [
            m for m in flex_res.messages
            if "less than ACI minimum As_min" not in m
        ]

        return CombinedFootingDesignResult(
            length=length_ft,
            width=b_ft,
            thickness=self.thickness,
            soil_pressure=round(q_actual, 2),
            allowable_pressure=self.allowable_q,
            punching_shear_col1=punch_1,
            punching_shear_col2=punch_2,
            one_way_shear=shear_1way,
            longitudinal_flexure=flex_res,
            top_steel_bars=f"{num_top_bars} {self.bar_size}",
            bottom_steel_bars=f"{num_bot_bars} {self.bar_size}",
            status=status,
            messages=messages + flex_clean_messages + shear_1way.messages + punch_1.messages + punch_2.messages,
            detailing=detail_obj,
        )
