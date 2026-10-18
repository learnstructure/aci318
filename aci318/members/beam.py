import copy
import math
from typing import Optional

from aci318.codes.base import DesignCode
from aci318.database.bars import BAR_DATABASE, Rebar
from aci318.detailing.beam import create_beam_detail_from_design_result
from aci318.loads.load_effects import LoadEffects
from aci318.materials.steel import Steel
from aci318.results.beam import BeamCheckResult, BeamDesignResult
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
        self.fy_shear = fy_shear

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
            torsion_checker = TorsionStrength(self.section, self.code)
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
        
        Args:
            loads: LoadEffects instance containing Mu, Vu, Tu.
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

        effective_depth = self.section.tension_steel[1] if self.section.tension_steel[1] > 0.0 else h - 2.5
        min_steel_ratio = self.code.get_minimum_steel_ratio(fc, fy_flexure)
        min_As = min_steel_ratio * b * effective_depth

        messages = []
        status = "Passed"
        required_As = 0.0
        suggested_bars = "None"
        provided_As = 0.0
        suggested_spacing = self.stirrup_spacing
        final_trial_section = copy.deepcopy(self.section)

        if Mu <= 0.0:
            required_As = min_As
            suggested_bars = "None"
            provided_As = 0.0
        else:
            candidate_sizes = ["#4", "#5", "#6", "#7", "#8", "#9", "#10", "#11"]
            cover = 1.5
            stirrup_d = 0.375
            b_clear = b - 2.0 * (cover + stirrup_d)
            selected_trial = None

            for size in candidate_sizes:
                db = BAR_DATABASE[size]["diameter"]
                ab = BAR_DATABASE[size]["area"]
                for n in range(2, 9):
                    area = n * ab
                    if area < min_As:
                        continue

                    s_clear_req = max(1.0, db)
                    req_w = n * db + (n - 1) * s_clear_req
                    if req_w > b_clear:
                        continue

                    trial_sec = copy.deepcopy(self.section)
                    trial_sec.layers = []
                    trial_sec.add_rebar_layer(
                        area=area,
                        depth=effective_depth,
                        steel=Steel(fy=fy_flexure),
                        num_bars=n,
                        bar_size=size,
                    )

                    flexure_res = FlexureStrength(trial_sec, self.code).check(loads)
                    if flexure_res.demand_capacity_ratio > 1.0:
                        continue

                    # Cross-section shear capacity limit (ACI 318 §22.5.1.2: Vs <= 8*sqrt(fc)*bw*d)
                    lambda_val = self.code.get_lambda_(self.section.concrete)
                    phi_shear = self.code.get_phi_shear()
                    fc_psi = fc * 1000.0
                    Vc_trial = self.code.get_vc(fc, b, effective_depth, loads.Pu, lambda_val=lambda_val)
                    Vs_max_trial = (8.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0
                    if Vu > phi_shear * (Vc_trial + Vs_max_trial):
                        continue

                    selected_trial = (size, n, area, trial_sec, flexure_res)
                    break
                if selected_trial is not None:
                    break

            if selected_trial is None:
                status = "Failed"
                messages.append("No reinforcement layout satisfied the demand-capacity constraints.")
            else:
                size, n, area, trial_sec, flexure_res = selected_trial
                required_As = min_As
                provided_As = area
                suggested_bars = f"{n} {size}"
                final_trial_section = trial_sec

                if flexure_res.status == "Failed":
                    status = "Failed"
                elif flexure_res.status == "Warning":
                    status = "Warning"

                messages.extend(flexure_res.messages)

        # Shear & Torsion Stirrup Spacing Determination
        torsion_res = None
        if status != "Failed" and Vu > 0.0:
            stirrup_rebar = Rebar(bar_size=self.stirrup_bar_size)
            av = self.stirrup_legs * stirrup_rebar.area
            lambda_val = self.code.get_lambda_(self.section.concrete)
            phi_shear = self.code.get_phi_shear()
            fc_psi = fc * 1000.0

            Vc = self.code.get_vc(fc, b, effective_depth, loads.Pu, lambda_val=lambda_val)
            Vs_req = max(0.0, (Vu / phi_shear) - Vc)
            Vs_max = (8.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0

            if Vs_req > Vs_max:
                status = "Failed"
                messages.append(f"Shear requirement Vs_req ({Vs_req:.1f} kip) exceeds maximum allowed Vs_max ({Vs_max:.1f} kip).")
                suggested_spacing = 0.0
            else:
                s_strength = (av * self.fy_shear * effective_depth / Vs_req) if Vs_req > 0 else float("inf")
                fy_shear_psi = self.fy_shear * 1000.0
                denom = max(0.75 * math.sqrt(fc_psi), 50.0) * b
                s_min_reinforcement = (av * fy_shear_psi) / denom

                limit_4_sqrt = (4.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0
                s_max = min(effective_depth / 2.0, 24.0) if Vs_req <= limit_4_sqrt else min(effective_depth / 4.0, 12.0)

                s_design = min(s_strength, s_min_reinforcement, s_max)
                suggested_spacing = math.floor(s_design * 2.0) / 2.0
                if suggested_spacing < 3.0:
                    suggested_spacing = 3.0

                shear_res = ShearStrength(
                    final_trial_section,
                    self.code,
                    av=av,
                    s=suggested_spacing,
                    fy_shear=self.fy_shear,
                ).check(LoadEffects(Vu=Vu))
                if shear_res.status == "Failed":
                    status = "Failed"
                elif shear_res.status == "Warning" and status != "Failed":
                    status = "Warning"
                messages.extend(shear_res.messages)

        if Tu > 0.0:
            torsion_checker = TorsionStrength(final_trial_section, self.code)
            torsion_res = torsion_checker.check(loads)
            if torsion_res.status == "Failed":
                status = "Failed"
            messages.extend(torsion_res.messages)

        res = BeamDesignResult(
            required_flexure_As=required_As,
            suggested_bars=suggested_bars,
            provided_flexure_As=provided_As,
            required_shear_spacing=suggested_spacing,
            stirrup_bar_size=self.stirrup_bar_size,
            stirrup_legs=self.stirrup_legs,
            status=status,
            messages=messages,
            trial_section=final_trial_section,
            torsion=torsion_res,
        )

        # Generate detailing object
        detailing_obj = create_beam_detail_from_design_result(
            design_result=res,
            member_id=self.member_id,
        )
        res.detailing = detailing_obj

        return res
