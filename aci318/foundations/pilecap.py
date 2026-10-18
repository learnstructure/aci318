"""
Pile cap foundation design coordinator according to ACI 318-19 Chapters 13 & 22.
Evaluates individual pile reactions, two-way punching shear around the column and piles,
one-way beam shear in orthogonal directions, and flexural reinforcement.
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
from aci318.results.footing import PileCapDesignResult
from aci318.results.shear import ShearResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.validators.loads import validate_load_effects

__all__ = [
    "PileCap",
    "PileCapDesignResult",
]


class PileCap:
    """
    Reinforced concrete pile cap design coordinator (ACI 318-19).
    """

    def __init__(
        self,
        length: float,                                # Cap length L along X in feet
        width: float,                                 # Cap width B along Y in feet
        thickness: float,                             # Cap thickness H in inches
        col_c1: float,                                # Column dimension along X in inches
        col_c2: float,                                # Column dimension along Y in inches
        concrete: Concrete,
        steel: Steel,
        code: DesignCode,
        pile_diameter: float = 12.0,                  # Pile diameter in inches
        pile_coordinates: Optional[List[Tuple[float, float]]] = None,  # (x_ft, y_ft) from cap centroid
        num_piles: int = 4,                           # Used if pile_coordinates not explicitly provided
        pile_capacity: float = 150.0,                 # Nominal/factored axial pile capacity in kips
        cover: float = 3.0,                           # Clear cover in inches (cast against earth/pile)
        bar_size: str = "#8",
        member_id: str = "pilecap-01",
    ) -> None:
        self.length = float(length)
        self.width = float(width)
        self.thickness = float(thickness)
        self.col_c1 = float(col_c1)
        self.col_c2 = float(col_c2)
        self.concrete = concrete
        self.steel = steel
        self.code = code
        self.pile_diameter = float(pile_diameter)
        self.pile_capacity = float(pile_capacity)
        self.cover = float(cover)
        self.bar_size = bar_size
        self.member_id = member_id

        if pile_coordinates is not None and len(pile_coordinates) > 0:
            self.pile_coordinates = list(pile_coordinates)
        else:
            self.pile_coordinates = self._generate_default_pile_pattern(num_piles)

    def _generate_default_pile_pattern(self, n: int) -> List[Tuple[float, float]]:
        """Generate symmetrical standard pile layout coordinates in feet from centroid."""
        edge_x = max(self.length / 2.0 - 1.25, 1.0)
        edge_y = max(self.width / 2.0 - 1.25, 1.0)

        if n == 2:
            return [(-edge_x * 0.75, 0.0), (edge_x * 0.75, 0.0)]
        elif n == 3:
            return [(0.0, edge_y * 0.75), (-edge_x * 0.75, -edge_y * 0.5), (edge_x * 0.75, -edge_y * 0.5)]
        elif n == 5:
            return [
                (-edge_x * 0.75, -edge_y * 0.75),
                (edge_x * 0.75, -edge_y * 0.75),
                (-edge_x * 0.75, edge_y * 0.75),
                (edge_x * 0.75, edge_y * 0.75),
                (0.0, 0.0),
            ]
        # Default 4-pile rectangular array
        return [
            (-edge_x * 0.75, -edge_y * 0.75),
            (edge_x * 0.75, -edge_y * 0.75),
            (-edge_x * 0.75, edge_y * 0.75),
            (edge_x * 0.75, edge_y * 0.75),
        ]

    def design(self, loads: LoadEffects) -> PileCapDesignResult:
        """
        Design pile cap for factored column axial, shear, and moment loads.
        
        Args:
            loads: LoadEffects containing Pu (kip), Mu (kip-in), Vu (kip).
            
        Returns:
            PileCapDesignResult dataclass.
        """
        validate_load_effects(loads)

        pu = max(loads.Pu, 0.0)
        mux_kipin = abs(loads.Mu2 if loads.Mu2 != 0.0 else loads.Mu)
        muy_kipin = abs(loads.Mu3)
        mux_ft = mux_kipin / 12.0
        muy_ft = muy_kipin / 12.0

        n_piles = len(self.pile_coordinates)
        sum_x2 = sum(x ** 2 for x, _ in self.pile_coordinates)
        sum_y2 = sum(y ** 2 for _, y in self.pile_coordinates)

        # 1. Pile reactions: R_i = P/N + (Muy*x / sum_x2) + (Mux*y / sum_y2)
        pile_reactions: List[float] = []
        for x, y in self.pile_coordinates:
            r = pu / max(n_piles, 1)
            if sum_x2 > 1e-4:
                r += (muy_ft * x) / sum_x2
            if sum_y2 > 1e-4:
                r += (mux_ft * y) / sum_y2
            pile_reactions.append(r)

        max_pile_reaction = max(pile_reactions) if pile_reactions else 0.0
        min_pile_reaction = min(pile_reactions) if pile_reactions else 0.0

        status = "Passed"
        messages = []

        if max_pile_reaction > self.pile_capacity:
            status = "Failed"
            messages.append(
                f"Peak pile reaction ({max_pile_reaction:.1f} kip) exceeds allowable capacity ({self.pile_capacity:.1f} kip)."
            )
        if min_pile_reaction < 0.0:
            messages.append(f"Net uplift tension occurs in pile ({min_pile_reaction:.1f} kip). Check pile pullout anchorage.")

        rebar = Rebar(bar_size=self.bar_size)
        d = max(self.thickness - self.cover - rebar.diameter, 1.0)
        lambda_val = self.code.get_lambda_(self.concrete)
        phi_v = self.code.get_phi_shear()
        fc_psi = self.concrete.fc * 1000.0

        # Size effect factor for two-way shear
        lambda_s = min(math.sqrt(2.0 / (1.0 + d / 10.0)), 1.0)

        # 2. Punching shear around column at d/2
        b1_col = self.col_c1 + d
        b2_col = self.col_c2 + d
        bo_col = 2.0 * (b1_col + b2_col)
        beta_c = max(self.col_c1 / max(self.col_c2, 1.0), self.col_c2 / max(self.col_c1, 1.0))
        alpha_s = 40.0

        v_c2_1 = (2.0 + 4.0 / beta_c) * lambda_s * lambda_val * math.sqrt(fc_psi)
        v_c2_2 = (alpha_s * d / bo_col + 2.0) * lambda_s * lambda_val * math.sqrt(fc_psi)
        v_c2_3 = 4.0 * lambda_s * lambda_val * math.sqrt(fc_psi)
        vc_col_stress = min(v_c2_1, v_c2_2, v_c2_3)
        vc_col_kip = (vc_col_stress * bo_col * d) / 1000.0
        phi_vc_col = phi_v * vc_col_kip

        # Piles outside column critical section contribute to punching shear
        col_half_x_ft = (b1_col / 2.0) / 12.0
        col_half_y_ft = (b2_col / 2.0) / 12.0
        vu_col_punch = sum(
            max(r, 0.0)
            for (x, y), r in zip(self.pile_coordinates, pile_reactions)
            if abs(x) > col_half_x_ft or abs(y) > col_half_y_ft
        )
        if vu_col_punch <= 0.0:
            vu_col_punch = pu

        dcr_col_punch = vu_col_punch / max(phi_vc_col, 0.1)
        punching_col_res = ShearResult(
            vn_concrete=vc_col_kip,
            vn_steel=0.0,
            phi_vn=phi_vc_col,
            required_spacing=0.0,
            status="Passed" if dcr_col_punch <= 1.0 else "Failed",
            messages=[] if dcr_col_punch <= 1.0 else [f"Column punching shear DCR {dcr_col_punch:.2f} > 1.0."],
            demand_capacity_ratio=dcr_col_punch,
        )

        # 3. Punching shear around single pile at d/2
        bo_pile = math.pi * (self.pile_diameter + d)
        vc_pile_stress = 4.0 * lambda_s * lambda_val * math.sqrt(fc_psi)
        vc_pile_kip = (vc_pile_stress * bo_pile * d) / 1000.0
        phi_vc_pile = phi_v * vc_pile_kip
        vu_pile_punch = max(max_pile_reaction, 0.0)
        dcr_pile_punch = vu_pile_punch / max(phi_vc_pile, 0.1)

        punching_pile_res = ShearResult(
            vn_concrete=vc_pile_kip,
            vn_steel=0.0,
            phi_vn=phi_vc_pile,
            required_spacing=0.0,
            status="Passed" if dcr_pile_punch <= 1.0 else "Failed",
            messages=[] if dcr_pile_punch <= 1.0 else [f"Individual pile punching shear DCR {dcr_pile_punch:.2f} > 1.0."],
            demand_capacity_ratio=dcr_pile_punch,
        )

        # 4. One-way shear at distance d from column face
        crit_x_ft = ((self.col_c1 / 2.0) + d) / 12.0
        vu_1way_x = sum(
            max(r, 0.0)
            for (x, _), r in zip(self.pile_coordinates, pile_reactions)
            if abs(x) > crit_x_ft
        )
        bw_y_in = self.width * 12.0
        rho_est = max(0.0018 * self.thickness / d, 0.0015)
        vc_1way_x = self.code.get_vc(
            f_c=self.concrete.fc,
            b_w=bw_y_in,
            d=d,
            N_u=0.0,
            A_g=bw_y_in * self.thickness,
            A_v=0.0,
            A_v_min=0.0,
            lambda_val=lambda_val,
            rho_w=rho_est,
        )
        phi_vc_1way_x = phi_v * vc_1way_x
        dcr_1way_x = vu_1way_x / max(phi_vc_1way_x, 0.1)

        one_way_x_res = ShearResult(
            vn_concrete=vc_1way_x,
            vn_steel=0.0,
            phi_vn=phi_vc_1way_x,
            required_spacing=0.0,
            status="Passed" if dcr_1way_x <= 1.0 else "Failed",
            messages=[] if dcr_1way_x <= 1.0 else [f"One-way shear X DCR {dcr_1way_x:.2f} > 1.0."],
            demand_capacity_ratio=dcr_1way_x,
        )

        crit_y_ft = ((self.col_c2 / 2.0) + d) / 12.0
        vu_1way_y = sum(
            max(r, 0.0)
            for (_, y), r in zip(self.pile_coordinates, pile_reactions)
            if abs(y) > crit_y_ft
        )
        bw_x_in = self.length * 12.0
        vc_1way_y = self.code.get_vc(
            f_c=self.concrete.fc,
            b_w=bw_x_in,
            d=d,
            N_u=0.0,
            A_g=bw_x_in * self.thickness,
            A_v=0.0,
            A_v_min=0.0,
            lambda_val=lambda_val,
            rho_w=rho_est,
        )
        phi_vc_1way_y = phi_v * vc_1way_y
        dcr_1way_y = vu_1way_y / max(phi_vc_1way_y, 0.1)

        one_way_y_res = ShearResult(
            vn_concrete=vc_1way_y,
            vn_steel=0.0,
            phi_vn=phi_vc_1way_y,
            required_spacing=0.0,
            status="Passed" if dcr_1way_y <= 1.0 else "Failed",
            messages=[] if dcr_1way_y <= 1.0 else [f"One-way shear Y DCR {dcr_1way_y:.2f} > 1.0."],
            demand_capacity_ratio=dcr_1way_y,
        )

        # 5. Flexure design at column face
        face_x_ft = (self.col_c1 / 2.0) / 12.0
        mu_x_kipin = sum(
            max(r, 0.0) * (abs(x) - face_x_ft) * 12.0
            for (x, _), r in zip(self.pile_coordinates, pile_reactions)
            if abs(x) > face_x_ft
        )

        face_y_ft = (self.col_c2 / 2.0) / 12.0
        mu_y_kipin = sum(
            max(r, 0.0) * (abs(y) - face_y_ft) * 12.0
            for (_, y), r in zip(self.pile_coordinates, pile_reactions)
            if abs(y) > face_y_ft
        )

        # Minimum reinforcement: 0.0018 * b * h (ACI 318-19 §13.3.2.1)
        as_min_x = 0.0018 * bw_y_in * self.thickness
        as_min_y = 0.0018 * bw_x_in * self.thickness

        a_approx = 1.0
        as_req_x = max(mu_x_kipin / (0.90 * self.steel.fy * max(d - a_approx / 2.0, 1.0)), as_min_x)
        as_req_y = max(mu_y_kipin / (0.90 * self.steel.fy * max(d - a_approx / 2.0, 1.0)), as_min_y)

        num_bars_x = max(int(math.ceil(as_req_x / rebar.area)), 4)
        num_bars_y = max(int(math.ceil(as_req_y / rebar.area)), 4)
        as_prov_x = num_bars_x * rebar.area
        as_prov_y = num_bars_y * rebar.area

        sec_x = RectangleSection(b=bw_y_in, h=self.thickness, concrete=self.concrete)
        sec_x.add_rebar_layer(area=as_prov_x, depth=d, steel=self.steel, num_bars=num_bars_x, bar_size=self.bar_size)
        flex_x = FlexureStrength(sec_x, self.code).check(LoadEffects(Mu=mu_x_kipin))

        sec_y = RectangleSection(b=bw_x_in, h=self.thickness, concrete=self.concrete)
        sec_y.add_rebar_layer(area=as_prov_y, depth=d, steel=self.steel, num_bars=num_bars_y, bar_size=self.bar_size)
        flex_y = FlexureStrength(sec_y, self.code).check(LoadEffects(Mu=mu_y_kipin))

        if (
            dcr_col_punch > 1.0
            or dcr_pile_punch > 1.0
            or dcr_1way_x > 1.0
            or dcr_1way_y > 1.0
            or flex_x.demand_capacity_ratio > 1.0
            or flex_y.demand_capacity_ratio > 1.0
        ):
            status = "Failed"

        return PileCapDesignResult(
            length=self.length,
            width=self.width,
            thickness=self.thickness,
            num_piles=n_piles,
            max_pile_reaction=max_pile_reaction,
            allowable_pile_capacity=self.pile_capacity,
            punching_shear_column=punching_col_res,
            punching_shear_pile=punching_pile_res,
            one_way_shear_x=one_way_x_res,
            one_way_shear_y=one_way_y_res,
            flexure_x=flex_x,
            flexure_y=flex_y,
            required_As_x=as_req_x,
            required_As_y=as_req_y,
            status=status,
            messages=messages + punching_col_res.messages + punching_pile_res.messages + one_way_x_res.messages + one_way_y_res.messages,
        )
