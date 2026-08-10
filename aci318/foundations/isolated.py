import math
from typing import Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.detailing.footing import create_footing_detail
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.flexure import FlexureResult
from aci318.results.footing import FootingDesignResult
from aci318.results.shear import ShearResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.validators.loads import validate_load_effects


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

    def design(self, loads: LoadEffects) -> FootingDesignResult:
        """
        Perform soil bearing check, one-way shear, two-way punching shear, and flexural steel design.
        
        Args:
            loads: Service and factored loads (Pu in kip, Mu in kip-in or kip-ft).
            
        Returns:
            FootingDesignResult dataclass.
        """
        validate_load_effects(loads)

        Pu = max(loads.Pu, 0.0)
        Mu_ft = abs(loads.Mu) / 12.0 if abs(loads.Mu) > 500.0 else abs(loads.Mu)

        # Footing area and section modulus
        area_ft2 = self.length * self.width
        sx_ft3 = (self.width * (self.length ** 2)) / 6.0

        # Soil bearing pressure (ksf)
        q_avg = Pu / area_ft2 if area_ft2 > 0 else 0.0
        q_ecc = Mu_ft / sx_ft3 if sx_ft3 > 0 else 0.0
        q_max = q_avg + q_ecc

        status = "Passed"
        messages = []

        if q_max > self.allowable_q:
            status = "Warning"
            messages.append(f"Maximum soil bearing pressure ({q_max:.2f} ksf) exceeds allowable capacity ({self.allowable_q:.2f} ksf).")

        rebar = Rebar(bar_size=self.bar_size)
        d = self.thickness - self.cover - rebar.diameter

        # Ultimate soil net pressure (ksf -> psi)
        qu_ksf = max(q_max * 1.2, 0.1)
        qu_psi = (qu_ksf * 1000.0) / 144.0

        # One-way shear check
        l_cant_in = max(((self.length * 12.0) - self.col_c1) / 2.0 - d, 0.0)
        vu1_lb = qu_psi * (self.width * 12.0) * l_cant_in
        vu1_kip = vu1_lb / 1000.0

        fc_psi = self.concrete.fc * 1000.0
        lambda_val = self.code.get_lambda_(self.concrete)
        phi_v = self.code.get_phi_shear()
        vc1_kip = (2.0 * lambda_val * math.sqrt(fc_psi) * (self.width * 12.0) * d) / 1000.0
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

        # Two-way punching shear check
        b1 = self.col_c1 + d
        b2 = self.col_c2 + d
        bo = 2.0 * b1 + 2.0 * b2

        punching_area_in2 = b1 * b2
        footing_area_in2 = self.length * 12.0 * self.width * 12.0
        vu2_lb = qu_psi * max(footing_area_in2 - punching_area_in2, 0.0)
        vu2_kip = vu2_lb / 1000.0

        beta_c = max(self.col_c1 / max(self.col_c2, 1.0), self.col_c2 / max(self.col_c1, 1.0))
        alpha_s = 40.0

        v_c2_1 = (2.0 + 4.0 / beta_c) * lambda_val * math.sqrt(fc_psi)
        v_c2_2 = (alpha_s * d / bo + 2.0) * lambda_val * math.sqrt(fc_psi)
        v_c2_3 = 4.0 * lambda_val * math.sqrt(fc_psi)
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
        mu_x_kipin = (qu_psi * (self.width * 12.0) * (cant_x_in ** 2) / 2.0) / 1000.0

        cant_y_in = max(((self.width * 12.0) - self.col_c2) / 2.0, 0.0)
        mu_y_kipin = (qu_psi * (self.length * 12.0) * (cant_y_in ** 2) / 2.0) / 1000.0

        # Flexural steel area calculations
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

        if dcr_1way > 1.0 or dcr_2way > 1.0 or flex_x.demand_capacity_ratio > 1.0 or flex_y.demand_capacity_ratio > 1.0:
            status = "Failed"

        from aci318.detailing.base import BarPlacement

        bars = [
            BarPlacement(id=f"{self.member_id}-bot-x", bar_size=self.bar_size, count=num_bars_x, location="bottom_x", cover=self.cover),
            BarPlacement(id=f"{self.member_id}-bot-y", bar_size=self.bar_size, count=num_bars_y, location="bottom_y", cover=self.cover),
        ]
        detailing_obj = create_footing_detail(member_id=self.member_id, bottom_bars=bars)

        return FootingDesignResult(
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
            messages=messages + flex_x.messages + flex_y.messages,
            detailing=detailing_obj,
        )
