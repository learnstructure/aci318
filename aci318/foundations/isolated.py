from __future__ import annotations

import math
from typing import Any, List, Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.detailing.footing import create_isolated_footing_detail
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.flexure import FlexureResult
from aci318.results.footing import IsolatedFootingDesignResult
from aci318.results.shear import ShearResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.validators.loads import validate_load_effects

__all__ = [
    "IsolatedFooting",
    "IsolatedFootingDesignResult",
]


class IsolatedFooting:
    """
    Isolated spread footing design coordinator according to ACI 318-19 Chapter 13 & 22.
    """

    def __init__(
        self,
        length: float,            # Footing length L in feet
        width: float,             # Footing width B in feet
        thickness: float,         # Footing thickness H in inches
        col_c1: float,            # Column dimension c1 (parallel to L) in inches
        col_c2: float,            # Column dimension c2 (parallel to B) in inches
        concrete: Concrete,
        steel: Steel,
        code: DesignCode,
        allowable_q: float = 5.0, # Allowable soil bearing capacity in ksf
        cover: float = 3.0,       # Cast against soil clear cover in inches
        bar_size: str = "#6",
        member_id: str = "ftg-01",
    ) -> None:
        self.length = length
        self.width = width
        self.thickness = thickness
        self.col_c1 = col_c1
        self.col_c2 = col_c2
        self.concrete = concrete
        self.steel = steel
        self.code = code
        self.allowable_q = allowable_q
        self.cover = cover
        self.bar_size = bar_size
        self.member_id = member_id

    def design(self, loads: LoadEffects) -> IsolatedFootingDesignResult:
        """
        Perform soil bearing check, one-way shear, two-way punching shear, and flexural steel design.
        
        Args:
            loads: Service and factored loads (Pu in kip, Mu in kip-in or kip-ft).
            
        Returns:
            IsolatedFootingDesignResult dataclass.
        """
        validate_load_effects(loads)

        Pu = max(loads.Pu, 0.0)
        # LoadEffects contract specifies moments in kip-in
        Mu_kipin = abs(loads.Mu2 if loads.Mu2 != 0.0 else loads.Mu)
        Mu_ft = Mu_kipin / 12.0
        Mu3_kipin = abs(loads.Mu3)
        Mu3_ft = Mu3_kipin / 12.0

        # Footing area and section modulus
        area_ft2 = self.length * self.width

        status = "Passed"
        messages = []

        # Soil bearing pressure (ksf) with kern & lift-off check
        q_avg = Pu / max(area_ft2, 0.01) if area_ft2 > 0 else 0.0
        q_ecc_y = 0.0
        if Pu > 0.0 and area_ft2 > 0.0:
            ex = Mu_ft / Pu
            ey = Mu3_ft / Pu

            if ex <= self.length / 6.0:
                q_max_x = q_avg * (1.0 + 6.0 * ex / self.length)
            elif ex < self.length / 2.0:
                # Triangular bearing with lift-off (contact length = 3 * (L/2 - ex))
                q_max_x = (2.0 * Pu) / (3.0 * self.width * max(self.length / 2.0 - ex, 0.01))
            else:
                q_max_x = 999.0
                status = "Failed"
                messages.append(f"Footing is unstable against overturning in X-direction (eccentricity e={ex:.2f} ft >= L/2={self.length/2.0:.2f} ft).")

            if ey <= self.width / 6.0:
                q_ecc_y = q_avg * (6.0 * ey / self.width)
            elif ey < self.width / 2.0:
                q_ecc_y = ((2.0 * Pu) / (3.0 * self.length * max(self.width / 2.0 - ey, 0.01))) - q_avg
            else:
                q_ecc_y = 999.0
                status = "Failed"
                messages.append(f"Footing is unstable against overturning in Y-direction (eccentricity e={ey:.2f} ft >= B/2={self.width/2.0:.2f} ft).")

            q_max = q_max_x + max(q_ecc_y, 0.0)
            q_ecc = max(q_max_x - q_avg, 0.0)
        else:
            q_max = 0.0
            q_ecc = 0.0

        if q_max > self.allowable_q:
            if status != "Failed":
                status = "Warning"
            messages.append(f"Maximum soil bearing pressure ({q_max:.2f} ksf) exceeds allowable capacity ({self.allowable_q:.2f} ksf).")

        rebar = Rebar(bar_size=self.bar_size)
        d = self.thickness - self.cover - rebar.diameter

        # Ultimate net soil pressure (factored loads Pu, Mu)
        qu_avg = q_avg
        qu_ecc = q_ecc

        # One-way shear check at distance d from column face
        bw_in = self.width * 12.0
        cant_total_in = max(((self.length * 12.0) - self.col_c1) / 2.0, 0.0)
        l_shear_in = max(cant_total_in - d, 0.0)

        # Average soil pressure over critical shear tributary cantilever
        x_mid_ft = ((self.col_c1 / 2.0 + d) + (self.length * 12.0 / 2.0)) / 2.0 / 12.0
        qu_crit_ksf = qu_avg + qu_ecc * (x_mid_ft / (self.length / 2.0)) if self.length > 0 and l_shear_in > 0 else qu_avg
        qu_crit_psi = (qu_crit_ksf * 1000.0) / 144.0

        vu1_lb = qu_crit_psi * bw_in * l_shear_in
        vu1_kip = vu1_lb / 1000.0

        fc_psi = self.concrete.fc * 1000.0
        lambda_val = self.code.get_lambda_(self.concrete)
        phi_v = self.code.get_phi_shear()

        # ACI 318-19 Table 22.5.5.1 for members without shear reinforcement
        rho_w_est = max(0.0018 * self.thickness / max(d, 1.0), 0.0015)
        vc1_kip = self.code.get_vc(
            f_c=self.concrete.fc,
            b_w=bw_in,
            d=d,
            N_u=0.0,
            A_g=bw_in * self.thickness,
            A_v=0.0,
            A_v_min=0.0,
            lambda_val=lambda_val,
            rho_w=rho_w_est,
        )
        phi_vc1 = phi_v * vc1_kip

        dcr_1way = vu1_kip / phi_vc1 if phi_vc1 > 0 else 0.0
        one_way_shear = ShearResult(
            vn_concrete=vc1_kip,
            vn_steel=0.0,
            phi_vn=phi_vc1,
            required_spacing=0.0,
            status="Passed" if dcr_1way <= 1.0 else "Failed",
            messages=[] if dcr_1way <= 1.0 else [f"One-way shear DCR {dcr_1way:.2f} > 1.0."],
            demand_capacity_ratio=dcr_1way,
        )

        # Two-way punching shear check (ACI 318-19 Table 22.6.5.2)
        b1 = self.col_c1 + d
        b2 = self.col_c2 + d
        bo = 2.0 * b1 + 2.0 * b2

        punching_area_in2 = b1 * b2
        # Net downward punching shear demand: Column load Pu minus relieving upward soil reaction inside perimeter
        vu2_kip = max(Pu - (qu_avg * (punching_area_in2 / 144.0)), 0.0)

        beta_c = max(self.col_c1 / max(self.col_c2, 1.0), self.col_c2 / max(self.col_c1, 1.0))
        alpha_s = 40.0  # interior column

        # ACI 318-19 Table 22.6.5.2: Size effect factor lambda_s applies to two-way shear
        lambda_s = min(math.sqrt(2.0 / (1.0 + d / 10.0)), 1.0)

        v_c2_1 = (2.0 + 4.0 / beta_c) * lambda_s * lambda_val * math.sqrt(fc_psi)
        v_c2_2 = (alpha_s * d / bo + 2.0) * lambda_s * lambda_val * math.sqrt(fc_psi)
        v_c2_3 = 4.0 * lambda_s * lambda_val * math.sqrt(fc_psi)
        vc2_stress_psi = min(v_c2_1, v_c2_2, v_c2_3)

        vc2_kip = (vc2_stress_psi * bo * d) / 1000.0
        phi_vc2 = phi_v * vc2_kip

        dcr_2way = vu2_kip / phi_vc2 if phi_vc2 > 0 else 0.0
        punching_shear = ShearResult(
            vn_concrete=vc2_kip,
            vn_steel=0.0,
            phi_vn=phi_vc2,
            required_spacing=0.0,
            status="Passed" if dcr_2way <= 1.0 else "Failed",
            messages=[] if dcr_2way <= 1.0 else [f"Two-way punching shear DCR {dcr_2way:.2f} > 1.0."],
            demand_capacity_ratio=dcr_2way,
        )

        # Flexural moment at column face
        cant_x_in = max(((self.length * 12.0) - self.col_c1) / 2.0, 0.0)
        x_cent_ft = (self.col_c1 / 2.0 + cant_x_in / 2.0) / 12.0
        qu_x_ksf = qu_avg + qu_ecc * (x_cent_ft / (self.length / 2.0)) if self.length > 0 else qu_avg
        qu_x_psi = (qu_x_ksf * 1000.0) / 144.0
        mu_x_kipin = (qu_x_psi * (self.width * 12.0) * (cant_x_in ** 2) / 2.0) / 1000.0

        cant_y_in = max(((self.width * 12.0) - self.col_c2) / 2.0, 0.0)
        y_cent_ft = (self.col_c2 / 2.0 + cant_y_in / 2.0) / 12.0
        qu_y_ksf = qu_avg + q_ecc_y * (y_cent_ft / (self.width / 2.0)) if self.width > 0 else qu_avg
        qu_y_psi = (qu_y_ksf * 1000.0) / 144.0
        mu_y_kipin = (qu_y_psi * (self.length * 12.0) * (cant_y_in ** 2) / 2.0) / 1000.0

        # Flexural steel area calculations (ACI 318-19 §13.3.2.1: As_min = 0.0018 * b * h)
        as_min_x = 0.0018 * (self.width * 12.0) * self.thickness
        as_min_y = 0.0018 * (self.length * 12.0) * self.thickness

        a_approx = 1.0
        as_req_x = max(mu_x_kipin / (0.9 * self.steel.fy * max(d - a_approx / 2.0, 1.0)), as_min_x)
        as_req_y = max(mu_y_kipin / (0.9 * self.steel.fy * max(d - a_approx / 2.0, 1.0)), as_min_y)

        num_bars_x = max(int(math.ceil(as_req_x / rebar.area)), 4)
        num_bars_y = max(int(math.ceil(as_req_y / rebar.area)), 4)

        as_prov_x = num_bars_x * rebar.area
        as_prov_y = num_bars_y * rebar.area

        sec_x = RectangleSection(b=self.width * 12.0, h=self.thickness, concrete=self.concrete)
        sec_x.add_rebar_layer(area=as_prov_x, depth=d, steel=self.steel, num_bars=num_bars_x, bar_size=self.bar_size)
        flex_x = FlexureStrength(sec_x, self.code).check(LoadEffects(Mu=mu_x_kipin))

        sec_y = RectangleSection(b=self.length * 12.0, h=self.thickness, concrete=self.concrete)
        sec_y.add_rebar_layer(area=as_prov_y, depth=d, steel=self.steel, num_bars=num_bars_y, bar_size=self.bar_size)
        flex_y = FlexureStrength(sec_y, self.code).check(LoadEffects(Mu=mu_y_kipin))

        # Footings require As >= 0.0018*b*h (ACI 318-19 §13.3.2.1), filter out beam minimum warning
        flex_messages = [
            m for m in (flex_x.messages + flex_y.messages)
            if "less than ACI minimum As_min" not in m
        ]

        if dcr_1way > 1.0 or dcr_2way > 1.0 or flex_x.demand_capacity_ratio > 1.0 or flex_y.demand_capacity_ratio > 1.0:
            status = "Failed"

        from aci318.detailing.base import BarPlacement

        bars = [
            BarPlacement(id=f"{self.member_id}-bot-x", bar_size=self.bar_size, count=num_bars_x, location="bottom_x", cover=self.cover),
            BarPlacement(id=f"{self.member_id}-bot-y", bar_size=self.bar_size, count=num_bars_y, location="bottom_y", cover=self.cover),
        ]
        detailing_obj = create_isolated_footing_detail(member_id=self.member_id, bottom_bars=bars)

        return IsolatedFootingDesignResult(
            length=self.length,
            width=self.width,
            thickness=self.thickness,
            max_bearing_pressure=q_max,
            allowable_bearing_capacity=self.allowable_q,
            one_way_shear=one_way_shear,
            punching_shear=punching_shear,
            flexure_x=flex_x,
            flexure_y=flex_y,
            required_As_x=as_req_x,
            required_As_y=as_req_y,
            status=status,
            messages=messages + flex_messages,
            detailing=detailing_obj,
        )
