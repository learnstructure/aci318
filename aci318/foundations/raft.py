"""
Raft / Mat foundation design coordinator according to ACI 318-19 Chapters 13 & 22.
Evaluates gross soil bearing pressures, two-way punching shear around governing columns,
one-way beam shear across design strips, and top/bottom two-way flexural reinforcement.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple, Union

from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.flexure import FlexureResult
from aci318.results.footing import RaftFoundationDesignResult
from aci318.results.shear import ShearResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.validators.loads import validate_load_effects

__all__ = [
    "RaftFoundation",
    "RaftFoundationDesignResult",
]


class RaftFoundation:
    """
    Raft / Mat Foundation design coordinator (ACI 318-19).
    """

    def __init__(
        self,
        length: float,                      # Mat length L along X in feet
        width: float,                       # Mat width B along Y in feet
        thickness: float,                   # Mat thickness H in inches
        concrete: Concrete,
        steel: Steel,
        code: DesignCode,
        allowable_q: float = 4.0,           # Allowable soil bearing capacity in ksf
        col_c1: float = 24.0,               # Representative column dimension along X in inches
        col_c2: float = 24.0,               # Representative column dimension along Y in inches
        typical_span_ft: float = 20.0,      # Typical column center-to-center span in feet
        cover: float = 3.0,                 # Clear cover in inches
        top_bar_size: str = "#6",           # Top negative flexure bar size
        bottom_bar_size: str = "#7",        # Bottom positive flexure bar size
        member_id: str = "mat-01",
    ) -> None:
        self.length = float(length)
        self.width = float(width)
        self.thickness = float(thickness)
        self.concrete = concrete
        self.steel = steel
        self.code = code
        self.allowable_q = float(allowable_q)
        self.col_c1 = float(col_c1)
        self.col_c2 = float(col_c2)
        self.typical_span_ft = float(typical_span_ft)
        self.cover = float(cover)
        self.top_bar_size = top_bar_size
        self.bottom_bar_size = bottom_bar_size
        self.member_id = member_id

    def design(
        self,
        loads: LoadEffects,
        col_axial_kip: Optional[float] = None,
    ) -> RaftFoundationDesignResult:
        """
        Design mat foundation for factored building loads and critical column punching.
        
        Args:
            loads: Total factored building loads on mat (Pu in kip, Mu in kip-in).
            col_axial_kip: Factored axial load on governing column for punching check.
                           If None, estimated as Pu / estimated column bays.
                           
        Returns:
            RaftFoundationDesignResult dataclass.
        """
        validate_load_effects(loads)

        pu = max(loads.Pu, 0.0)
        mux_kipin = abs(loads.Mu2 if loads.Mu2 != 0.0 else loads.Mu)
        muy_kipin = abs(loads.Mu3)
        mux_ft = mux_kipin / 12.0
        muy_ft = muy_kipin / 12.0

        area_ft2 = self.length * self.width
        status = "Passed"
        messages = []

        # 1. Soil bearing pressure with kern check
        q_avg = pu / max(area_ft2, 0.01) if area_ft2 > 0 else 0.0
        if pu > 0.0 and area_ft2 > 0.0:
            ex = mux_ft / pu
            ey = muy_ft / pu

            if ex <= self.length / 6.0:
                q_max_x = q_avg * (1.0 + 6.0 * ex / self.length)
            elif ex < self.length / 2.0:
                q_max_x = (2.0 * pu) / (3.0 * self.width * max(self.length / 2.0 - ex, 0.01))
            else:
                q_max_x = 999.0
                status = "Failed"
                messages.append(f"Mat is unstable against overturning in X-direction (eccentricity e={ex:.2f} ft >= L/2={self.length/2.0:.2f} ft).")

            if ey <= self.width / 6.0:
                q_ecc_y = q_avg * (6.0 * ey / self.width)
            elif ey < self.width / 2.0:
                q_ecc_y = ((2.0 * pu) / (3.0 * self.length * max(self.width / 2.0 - ey, 0.01))) - q_avg
            else:
                q_ecc_y = 999.0
                status = "Failed"
                messages.append(f"Mat is unstable against overturning in Y-direction (eccentricity e={ey:.2f} ft >= B/2={self.width/2.0:.2f} ft).")

            q_max = q_max_x + max(q_ecc_y, 0.0)
        else:
            q_max = 0.0

        if q_max > self.allowable_q:
            if status != "Failed":
                status = "Warning"
            messages.append(f"Peak soil bearing pressure ({q_max:.2f} ksf) exceeds allowable capacity ({self.allowable_q:.2f} ksf).")

        bot_rebar = Rebar(bar_size=self.bottom_bar_size)
        top_rebar = Rebar(bar_size=self.top_bar_size)
        d_bot = max(self.thickness - self.cover - bot_rebar.diameter, 1.0)
        d_top = max(self.thickness - self.cover - top_rebar.diameter, 1.0)
        d_avg = (d_bot + d_top) / 2.0

        lambda_val = self.code.get_lambda_(self.concrete)
        phi_v = self.code.get_phi_shear()
        fc_psi = self.concrete.fc * 1000.0

        # 2. Punching shear at critical column
        est_bays = max(round((self.length / self.typical_span_ft) * (self.width / self.typical_span_ft)), 1)
        p_col = float(col_axial_kip) if col_axial_kip is not None else (pu / est_bays)

        b1 = self.col_c1 + d_avg
        b2 = self.col_c2 + d_avg
        bo = 2.0 * (b1 + b2)
        punch_area_in2 = b1 * b2

        # Net upward relief from soil inside punching perimeter
        vu_punch = max(p_col - (q_avg * (punch_area_in2 / 144.0)), 0.0)

        lambda_s = min(math.sqrt(2.0 / (1.0 + d_avg / 10.0)), 1.0)
        beta_c = max(self.col_c1 / max(self.col_c2, 1.0), self.col_c2 / max(self.col_c1, 1.0))
        alpha_s = 40.0  # interior column

        v_c2_1 = (2.0 + 4.0 / beta_c) * lambda_s * lambda_val * math.sqrt(fc_psi)
        v_c2_2 = (alpha_s * d_avg / bo + 2.0) * lambda_s * lambda_val * math.sqrt(fc_psi)
        v_c2_3 = 4.0 * lambda_s * lambda_val * math.sqrt(fc_psi)
        vc_punch_stress = min(v_c2_1, v_c2_2, v_c2_3)
        vc_punch_kip = (vc_punch_stress * bo * d_avg) / 1000.0
        phi_vc_punch = phi_v * vc_punch_kip

        dcr_punch = vu_punch / max(phi_vc_punch, 0.1)
        punching_res = ShearResult(
            vn_concrete=vc_punch_kip,
            vn_steel=0.0,
            phi_vn=phi_vc_punch,
            required_spacing=0.0,
            status="Passed" if dcr_punch <= 1.0 else "Failed",
            messages=[] if dcr_punch <= 1.0 else [f"Mat punching shear DCR {dcr_punch:.2f} > 1.0."],
            demand_capacity_ratio=dcr_punch,
        )

        # 3. One-way shear along 12-inch design strip at d from column face
        strip_b_in = 12.0
        qu_psi = (max(q_max, 0.01) * 1000.0) / 144.0
        shear_cant_in = max(((self.typical_span_ft * 12.0) - self.col_c1) / 2.0 - d_avg, 0.0)
        vu_1way_kip = (qu_psi * strip_b_in * shear_cant_in) / 1000.0

        rho_est = max(0.0018 * self.thickness / d_avg, 0.0015)
        vc_1way_kip = self.code.get_vc(
            f_c=self.concrete.fc,
            b_w=strip_b_in,
            d=d_avg,
            N_u=0.0,
            A_g=strip_b_in * self.thickness,
            A_v=0.0,
            A_v_min=0.0,
            lambda_val=lambda_val,
            rho_w=rho_est,
        )
        phi_vc_1way = phi_v * vc_1way_kip
        dcr_1way = vu_1way_kip / max(phi_vc_1way, 0.1)

        one_way_res = ShearResult(
            vn_concrete=vc_1way_kip,
            vn_steel=0.0,
            phi_vn=phi_vc_1way,
            required_spacing=0.0,
            status="Passed" if dcr_1way <= 1.0 else "Failed",
            messages=[] if dcr_1way <= 1.0 else [f"Mat one-way shear DCR {dcr_1way:.2f} > 1.0."],
            demand_capacity_ratio=dcr_1way,
        )

        # 4. Flexure: Positive bottom moment (under columns) and Negative top moment (between columns)
        # Using continuous plate / strip moment coefficients: M_pos = q * L^2 / 10, M_neg = q * L^2 / 12
        span_in = self.typical_span_ft * 12.0
        q_strip_lb_in = qu_psi * strip_b_in  # lb per in of strip length
        mu_pos_kipin = (q_strip_lb_in * (span_in ** 2) / 10.0) / 1000.0
        mu_neg_kipin = (q_strip_lb_in * (span_in ** 2) / 12.0) / 1000.0

        as_min_per_ft = 0.0018 * strip_b_in * self.thickness
        as_req_bot = max(mu_pos_kipin / (0.90 * self.steel.fy * max(d_bot - 0.5, 1.0)), as_min_per_ft)
        as_req_top = max(mu_neg_kipin / (0.90 * self.steel.fy * max(d_top - 0.5, 1.0)), as_min_per_ft)

        # Spacing calculations per foot
        num_bot_bars = max(int(math.ceil(as_req_bot / bot_rebar.area)), 2)
        num_top_bars = max(int(math.ceil(as_req_top / top_rebar.area)), 2)

        as_prov_bot = num_bot_bars * bot_rebar.area
        as_prov_top = num_top_bars * top_rebar.area

        sec_strip_bot = RectangleSection(b=strip_b_in, h=self.thickness, concrete=self.concrete)
        sec_strip_bot.add_rebar_layer(area=as_prov_bot, depth=d_bot, steel=self.steel, num_bars=num_bot_bars, bar_size=self.bottom_bar_size)
        flex_bot = FlexureStrength(sec_strip_bot, self.code).check(LoadEffects(Mu=mu_pos_kipin))

        sec_strip_top = RectangleSection(b=strip_b_in, h=self.thickness, concrete=self.concrete)
        sec_strip_top.add_rebar_layer(area=as_prov_top, depth=d_top, steel=self.steel, num_bars=num_top_bars, bar_size=self.top_bar_size)
        flex_top = FlexureStrength(sec_strip_top, self.code).check(LoadEffects(Mu=mu_neg_kipin))

        if (
            dcr_punch > 1.0
            or dcr_1way > 1.0
            or flex_bot.demand_capacity_ratio > 1.0
            or flex_top.demand_capacity_ratio > 1.0
        ):
            status = "Failed"

        return RaftFoundationDesignResult(
            length=self.length,
            width=self.width,
            thickness=self.thickness,
            max_bearing_pressure=q_max,
            allowable_bearing_capacity=self.allowable_q,
            punching_shear=punching_res,
            one_way_shear=one_way_res,
            flexure_top=flex_top,
            flexure_bottom=flex_bot,
            required_As_top=as_req_top,
            required_As_bottom=as_req_bot,
            status=status,
            messages=messages + punching_res.messages + one_way_res.messages,
        )
