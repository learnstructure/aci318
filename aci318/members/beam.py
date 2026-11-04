import copy
import math
from typing import Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import BAR_DATABASE, Rebar
from aci318.detailing.beam import create_beam_detail_from_design_result
from aci318.loads.load_effects import LoadEffects
from aci318.materials.steel import Steel
from aci318.results.beam import BeamCheckResult, BeamDesignResult
from aci318.results.shear import ShearResult
from aci318.results.torsion import TorsionResult
from aci318.sections.rectangle import RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.strength.torsion_strength import TorsionStrength
from aci318.validators.loads import validate_load_effects


class Beam:
    """
    User-facing Beam class coordinating calculations according to ACI 318.
    
    This class orchestrates strength checks and design workflows without
    directly implementing engineering equations (which reside in aci318.strength).
    """

    def __init__(
        self,
        section: RectangleSection,
        code: DesignCode,
        member_id: str = "beam-01",
        stirrup_bar_size: str = "#3",
        stirrup_spacing: float = 12.0,
        stirrup_legs: int = 2,
        fy_shear: float = 60.0,
    ) -> None:
        self.section = section
        self.code = code
        self.member_id = member_id
        self.stirrup_bar_size = stirrup_bar_size
        self.stirrup_spacing = stirrup_spacing
        self.stirrup_legs = stirrup_legs
        # Stirrups for shear and torsion: fyt limited to 60 ksi (Table 20.2.2.4(a))
        self.fy_shear = min(fy_shear, 60.0)
        self.steel = section.layers[0].steel if section.layers else Steel(fy=60.0)

    def check(self, loads: LoadEffects) -> BeamCheckResult:
        """
        Coordinates flexural, shear, and torsional strength checks for the beam.
        
        Args:
            loads: LoadEffects object containing Pu, Mu, Vu, Tu.
            
        Returns:
            BeamCheckResult dataclass.
        """
        validate_load_effects(loads)

        flexure_checker = FlexureStrength(self.section, self.code)
        flexure_res = flexure_checker.check(loads)

        stirrup_rebar = Rebar(bar_size=self.stirrup_bar_size)
        av = self.stirrup_legs * stirrup_rebar.area

        shear_checker = ShearStrength(
            self.section,
            self.code,
            av=av,
            s=self.stirrup_spacing,
            fy_shear=self.fy_shear,
        )
        shear_res = shear_checker.check(loads)

        torsion_res = None
        if abs(loads.Tu) > 0.0:
            torsion_checker = TorsionStrength(self.section, self.code, fyt=self.fy_shear)
            torsion_res = torsion_checker.check(loads)

        status = "Passed"
        if flexure_res.status == "Failed" or shear_res.status == "Failed" or (torsion_res and torsion_res.status == "Failed"):
            status = "Failed"
        elif flexure_res.status == "Warning" or shear_res.status == "Warning" or (torsion_res and torsion_res.status == "Warning"):
            status = "Warning"

        messages = flexure_res.messages + shear_res.messages
        if torsion_res:
            messages.extend(torsion_res.messages)

        return BeamCheckResult(
            flexure=flexure_res,
            shear=shear_res,
            torsion=torsion_res,
            status=status,
            messages=messages,
        )


    def design(self, loads: LoadEffects, fy_flexure: float = 60.0) -> BeamDesignResult:
        """
        Iteratively select longitudinal and transverse reinforcement without mutating self.section.

        - Flexure (§22.2): the first fitting layout with Mu <= phi*Mn that is tension-controlled
          (§9.3.3.1, net tensile strain >= epsilon_ty + 0.003).
        - Torsion (§22.7, §9.5.4): when Tu > phi*Tth the longitudinal torsion steel Al is added
          half to each face (the flexural layer keeps Al/2 in reserve), and every outer stirrup
          leg carries Av/(n s) + At/s.
        - Shear (§22.5, §9.6.3, §9.7.6.2.2): lightest stirrup arrangement with spacing >= 3 in.

        Args:
            loads: LoadEffects instance containing Mu, Vu, Tu (and Pu, compression positive).
            fy_flexure: Longitudinal steel yield strength in ksi.

        Returns:
            BeamDesignResult containing design outputs, non-mutated trial_section, and detailing object.
        """
        validate_load_effects(loads)

        b = getattr(self.section, "b_w", getattr(self.section, "b", 12.0))
        h = self.section.h
        fc = self.section.concrete.fc
        Mu = loads.Mu
        Vu = abs(loads.Vu)
        Tu = abs(loads.Tu)

        # Effective depth of a single layer of ``size`` bars: inside the section's clear cover and the stirrups
        # (unless the section already has its tension steel placed)
        cover = self.section.cover
        stirrup_d = Rebar(bar_size=self.stirrup_bar_size).diameter

        def depth_for(size: str) -> float:
            if self.section.tension_steel[1] > 0.0:
                return self.section.tension_steel[1]
            return h - cover - stirrup_d - BAR_DATABASE[size]["diameter"] / 2.0

        effective_depth = depth_for("#4")  # until bars are chosen
        min_steel_ratio = self.code.get_minimum_steel_ratio(fc, fy_flexure)
        min_As = min_steel_ratio * b * effective_depth
        eps_tc = self.code.get_tension_controlled_strain(fy_flexure)

        messages = []
        status = "Passed"
        required_As = 0.0
        suggested_bars = "None"
        provided_As = 0.0
        suggested_spacing = self.stirrup_spacing
        final_trial_section = copy.deepcopy(self.section)
        flexure_check = None
        shear_check = None
        ductility_ratio = None

        # Torsion demand first: it adds longitudinal steel to the flexural layer and transverse steel to the stirrups
        torsion_req = None
        if Tu > 0.0:
            torsion_req = TorsionStrength(self.section, self.code, fyt=self.fy_shear, fy=fy_flexure).check(loads)
            if torsion_req.tn_nominal <= 0.0:  # Tu <= phi*Tth: torsion may be neglected (§22.7.1.1)
                messages.extend(torsion_req.messages)
                torsion_req = None
        al_per_face = torsion_req.required_longitudinal_steel / 2.0 if torsion_req is not None else 0.0

        def _trial(size: str, n: int) -> tuple:
            area = n * BAR_DATABASE[size]["area"]
            trial_sec = copy.deepcopy(self.section)
            trial_sec.layers = []
            trial_sec.add_rebar_layer(
                area=max(area - al_per_face, 1e-6),
                depth=depth_for(size),
                steel=Steel(fy=fy_flexure, Es=self.steel.Es),
                num_bars=n,
                bar_size=size,
            )
            flexure_res = FlexureStrength(trial_sec, self.code).check(loads)
            ratio = max(flexure_res.demand_capacity_ratio, eps_tc / max(flexure_res.steel_strain, 1e-9))
            return area, trial_sec, flexure_res, ratio

        if Mu <= 0.0:
            required_As = min_As + al_per_face
            suggested_bars = "None"
            provided_As = 0.0
            if not final_trial_section.layers:
                final_trial_section.add_rebar_layer(
                    area=max(required_As, 1e-6),
                    depth=effective_depth,
                    steel=Steel(fy=fy_flexure, Es=self.steel.Es),
                )
        else:
            candidate_sizes = ["#4", "#5", "#6", "#7", "#8", "#9", "#10", "#11"]
            b_clear = b - 2.0 * (cover + stirrup_d)
            selected_trial = None
            strongest_trial = None  # fitting layout closest to passing, reported when nothing passes

            for size in candidate_sizes:
                db = BAR_DATABASE[size]["diameter"]
                for n in range(2, 9):
                    if n * BAR_DATABASE[size]["area"] - al_per_face < min_steel_ratio * b * depth_for(size):
                        continue
                    if n * db + (n - 1) * max(1.0, db) > b_clear:
                        continue

                    trial = (size, n) + _trial(size, n)
                    if strongest_trial is None or trial[5] < strongest_trial[5]:
                        strongest_trial = trial
                    if trial[4].demand_capacity_ratio <= 1.0 and trial[4].steel_strain >= eps_tc:
                        selected_trial = trial
                        break
                if selected_trial is not None:
                    break

            if selected_trial is None:
                status = "Failed"
                messages.append(
                    "No reinforcement layout that fits the section width resists the factored moment "
                    "as a tension-controlled section (ACI 318 §9.3.3.1)."
                )
                # No layout fits at all: report the two-bar #4 minimum so the DCR still reflects the demand
                strongest_trial = strongest_trial or ("#4", 2) + _trial("#4", 2)
                flexure_check = strongest_trial[4]
                if not final_trial_section.layers:
                    final_trial_section.add_rebar_layer(
                        area=max(min_As + al_per_face, 1e-6),
                        depth=effective_depth,
                        steel=Steel(fy=fy_flexure, Es=self.steel.Es),
                    )
            else:
                size, n, area, trial_sec, flexure_res, _ = selected_trial
                effective_depth = depth_for(size)
                min_As = min_steel_ratio * b * effective_depth
                required_As = min_As + al_per_face
                provided_As = area
                suggested_bars = f"{n} {size}"
                final_trial_section = trial_sec
                flexure_check = flexure_res

                if flexure_res.status == "Failed":
                    status = "Failed"
                elif flexure_res.status == "Warning":
                    status = "Warning"

                messages.extend(flexure_res.messages)
            ductility_ratio = eps_tc / max(flexure_check.steel_strain, 1e-9)

        # Shear & Torsion Stirrup Spacing Determination
        torsion_res = None
        stirrup_size, stirrup_legs = self.stirrup_bar_size, self.stirrup_legs
        if Vu > 0.0 or torsion_req is not None:
            lambda_val = self.code.get_lambda_(self.section.concrete)
            phi_shear = self.code.get_phi_shear()
            fc_psi = fc * 1000.0

            # Vc with the most tensile concurrent axial force (Pu <= 0 lowers Vc, Table 22.5.5.1);
            # the final stirrup check below uses the same axial force
            Ag = b * h
            nu = min(loads.Pu, 0.0)
            Vc = self.code.get_vc(fc, b, effective_depth, nu, A_g=Ag, A_v=1.0, A_v_min=0.0, lambda_val=lambda_val)
            Vs_req = max(0.0, (Vu / phi_shear) - Vc)
            # Cross-section shear capacity limit (ACI 318 §22.5.1.2: Vs <= 8*sqrt(fc)*bw*d)
            Vs_max = (8.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0

            if Vs_req > Vs_max:
                status = "Failed"
                msg = f"Shear requirement Vs_req ({Vs_req:.1f} kip) exceeds maximum allowed Vs_max ({Vs_max:.1f} kip)."
                messages.append(msg)
                suggested_spacing = 0.0
                phi_vn_max = phi_shear * (Vc + Vs_max)
                shear_check = ShearResult(
                    vn_concrete=Vc,
                    vn_steel=Vs_max,
                    phi_vn=phi_vn_max,
                    required_spacing=0.0,
                    status="Failed",
                    messages=[msg],
                    demand_capacity_ratio=Vu / phi_vn_max,
                )
            else:
                fy_shear_psi = self.fy_shear * 1000.0
                limit_4_sqrt = (4.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0
                s_max = min(effective_depth / 2.0, 24.0) if Vs_req <= limit_4_sqrt else min(effective_depth / 4.0, 12.0)

                av_s_req = Vs_req / (self.fy_shear * effective_depth)  # shear steel rate, in^2/in
                at_s_req = 0.0
                if torsion_req is not None:
                    at_s_req = torsion_req.required_transverse_steel  # per leg, in^2/in
                    ph = 2.0 * (b + h) - 8.0 * (self.section.cover + stirrup_d / 2.0)  # stirrup centerline perimeter
                    s_max = min(s_max, ph / 8.0, 12.0)  # §9.7.6.3.3

                # Lightest stirrup arrangement whose strength spacing is at least the 3 in practical minimum:
                # the configured stirrup first, then heavier bars, then four legs where the width allows.
                # Each outer leg carries its share of shear plus the torsion steel At/s.
                options = [(self.stirrup_bar_size, self.stirrup_legs), ("#4", 2), ("#5", 2)]
                if b >= 12.0:
                    options += [("#4", 4), ("#5", 4)]
                for stirrup_size, stirrup_legs in options:
                    leg_area = Rebar(bar_size=stirrup_size).area
                    av = stirrup_legs * leg_area
                    per_leg_rate = av_s_req / stirrup_legs + at_s_req
                    s_strength = leg_area / per_leg_rate if per_leg_rate > 0 else float("inf")
                    if s_strength >= 3.0:
                        break

                # Minimum transverse steel (Av + 2At)/s (§9.6.3.4, §9.6.4.2)
                min_rate = max(0.75 * math.sqrt(fc_psi), 50.0) * b / fy_shear_psi
                s_min_reinforcement = av / min_rate
                s_design = min(s_strength, s_min_reinforcement, s_max)
                suggested_spacing = max(3.0, math.floor(s_design * 2.0) / 2.0)

                shear_check = ShearStrength(
                    final_trial_section,
                    self.code,
                    av=av,
                    s=suggested_spacing,
                    fy_shear=self.fy_shear,
                ).check(LoadEffects(Vu=Vu, Pu=nu))
                if shear_check.status == "Failed":
                    status = "Failed"
                elif shear_check.status == "Warning" and status != "Failed":
                    status = "Warning"
                messages.extend(shear_check.messages)

                if torsion_req is not None:
                    torsion_res = self._torsion_with_stirrups(
                        torsion_req, Tu, leg_area, stirrup_legs, suggested_spacing, av_s_req
                    )

        if torsion_req is not None:
            if torsion_res is None:  # section limit on shear governs: no stirrup layout exists
                torsion_res = torsion_req
                torsion_res.status = "Failed"
            if torsion_res.status == "Failed":
                status = "Failed"
            messages.extend(torsion_res.messages)

        res = BeamDesignResult(
            required_flexure_As=required_As,
            suggested_bars=suggested_bars,
            provided_flexure_As=provided_As,
            required_shear_spacing=suggested_spacing,
            stirrup_bar_size=stirrup_size,
            stirrup_legs=stirrup_legs,
            status=status,
            messages=messages,
            trial_section=final_trial_section,
            flexure=flexure_check,
            shear=shear_check,
            torsion=torsion_res,
            ductility_ratio=ductility_ratio,
        )

        # Generate detailing object
        detailing_obj = create_beam_detail_from_design_result(
            design_result=res,
            member_id=self.member_id,
            cover=self.section.cover,
        )
        res.detailing = detailing_obj

        return res

    def _torsion_with_stirrups(
        self,
        torsion_req: TorsionResult,
        Tu: float,
        leg_area: float,
        legs: int,
        spacing: float,
        av_s_req: float,
    ) -> TorsionResult:
        """
        Torsion check with the provided stirrups (§22.7.6.1, theta = 45 deg).

        The outer closed legs give At/s = Ab/s - Av,req/(n s); Tn = 2 Ao (At/s) fyt.
        """
        at_s_prov = max(leg_area / spacing - av_s_req / legs, 0.0)
        tn_req = torsion_req.tn_nominal
        at_s_req = torsion_req.required_transverse_steel
        tn = tn_req * at_s_prov / at_s_req if at_s_req > 0.0 else 0.0  # Tn is linear in At/s
        phi_tn = self.code.get_phi_torsion() * tn
        ratio = Tu / phi_tn if phi_tn > 0.0 else float("inf")
        status = torsion_req.status
        messages = list(torsion_req.messages)
        if ratio > 1.0:
            status = "Failed"
            messages.append(f"Torsional demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        return TorsionResult(
            tn_nominal=tn,
            phi_tn=phi_tn,
            required_transverse_steel=at_s_req,
            required_longitudinal_steel=torsion_req.required_longitudinal_steel,
            threshold_torsion=torsion_req.threshold_torsion,
            cracking_torsion=torsion_req.cracking_torsion,
            status=status,
            messages=messages,
            demand_capacity_ratio=ratio,
        )
