import copy

from aci318.codes.base import DesignCode
from aci318.loads.load_effects import LoadEffects
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.results.beam import BeamCheckResult, BeamDesignResult
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.database.bars import Rebar


class Beam:
    """
    User-facing Beam class that coordinates calculations.
    It contains no structural design equations directly.
    """
    def __init__(
        self,
        section: RectangleSection,
        code: DesignCode,
        stirrup_bar_size: str = "#3",
        stirrup_spacing: float = 12.0,
        stirrup_legs: int = 2,
        fy_shear: float = 60.0
    ) -> None:
        self.section = section
        self.code = code
        self.stirrup_bar_size = stirrup_bar_size
        self.stirrup_spacing = stirrup_spacing
        self.stirrup_legs = stirrup_legs
        self.fy_shear = fy_shear

    def check(self, loads: LoadEffects) -> BeamCheckResult:
        """Coordinates flexural and shear strength checks for the beam."""
        flexure_checker = FlexureStrength(self.section, self.code)
        flexure_res = flexure_checker.check(loads)

        stirrup_rebar = Rebar(bar_size=self.stirrup_bar_size)
        av = self.stirrup_legs * stirrup_rebar.area

        shear_checker = ShearStrength(self.section, self.code)
        shear_res = shear_checker.check(loads)
        shear_res.required_spacing = self.stirrup_spacing
        shear_res.vn_steel = av * self.fy_shear * max(self.section.h - 2.5, 0.0) / self.stirrup_spacing if self.stirrup_spacing > 0 else 0.0

        status = "Passed"
        if flexure_res.status == "Failed" or shear_res.status == "Failed":
            status = "Failed"
        elif flexure_res.status == "Warning" or shear_res.status == "Warning":
            status = "Warning"

        messages = flexure_res.messages + shear_res.messages
        return BeamCheckResult(
            flexure=flexure_res,
            shear=shear_res,
            status=status,
            messages=messages,
        )

    # Alias for backward compatibility
    def design_old(self, loads: LoadEffects) -> BeamCheckResult:
        return self.check(loads)

    def design(self, loads: LoadEffects, fy_flexure: float = 60.0) -> BeamDesignResult:
        """Iteratively select longitudinal reinforcement using modular strength checks."""
        import math
        from aci318.database.bars import BAR_DATABASE

        b = self.section.b
        h = self.section.h
        fc = self.section.concrete.fc
        Mu = loads.Mu
        Vu = loads.Vu

        effective_depth = self.section.tension_steel[1] if self.section.tension_steel[1] > 0.0 else h - 2.5
        min_steel_ratio = self.code.get_minimum_steel_ratio(fc, fy_flexure)
        min_As = min_steel_ratio * b * effective_depth

        messages = []
        status = "Passed"
        required_As = 0.0
        suggested_bars = "None"
        provided_As = 0.0
        suggested_spacing = self.stirrup_spacing

        if Mu <= 0.0:
            required_As = 0.0
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

                    trial_section = copy.deepcopy(self.section)
                    trial_section.layers = []
                    trial_section.add_rebar_layer(
                        area=area,
                        depth=effective_depth,
                        steel=Steel(fy=fy_flexure),
                        num_bars=n,
                        bar_size=size,
                    )

                    flexure_res = FlexureStrength(trial_section, self.code).check(loads)
                    if flexure_res.demand_capacity_ratio > 1.0:
                        continue

                    stirrup_rebar = Rebar(bar_size=self.stirrup_bar_size)
                    av = self.stirrup_legs * stirrup_rebar.area
                    shear_res = ShearStrength(
                        trial_section,
                        self.code,
                        av=av,
                        s=self.stirrup_spacing,
                        fy_shear=self.fy_shear,
                    ).check(LoadEffects(Vu=Vu))
                    if shear_res.demand_capacity_ratio > 1.0:
                        continue

                    if flexure_res.demand_capacity_ratio > 0.85 or shear_res.demand_capacity_ratio > 0.85:
                        continue

                    selected_trial = (size, n, area, trial_section, flexure_res, shear_res)
                    break
                if selected_trial is not None:
                    break

            if selected_trial is None:
                status = "Failed"
                messages.append("No reinforcement layout satisfied the current demand-capacity checks.")
            else:
                size, n, area, trial_section, flexure_res, shear_res = selected_trial
                required_As = area
                provided_As = area
                suggested_bars = f"{n} {size}"
                self.section.layers = []
                self.section.layers.extend(trial_section.layers)

                if flexure_res.status == "Failed" or shear_res.status == "Failed":
                    status = "Failed"
                elif flexure_res.status == "Warning" or shear_res.status == "Warning" or shear_res.status == "Warning":
                    status = "Warning"

                messages.extend(flexure_res.messages)
                messages.extend(shear_res.messages)

        if status == "Passed" and Vu > 0.0:
            stirrup_rebar = Rebar(bar_size=self.stirrup_bar_size)
            av = self.stirrup_legs * stirrup_rebar.area
            lambda_val = self.code.get_lambda_(self.section.concrete)
            phi_shear = self.code.get_phi_shear()
            fc_psi = fc * 1000.0
            Vc = (2.0 * lambda_val * math.sqrt(fc_psi) * effective_depth * b) / 1000.0
            Vs_req = max(0.0, (Vu / phi_shear) - Vc)
            Vs_max = (8.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0
            if Vs_req > Vs_max:
                status = "Failed"
                messages.append(f"Shear reinforcement required Vs_req ({Vs_req:.1f} kip) exceeds maximum allowed Vs_max ({Vs_max:.1f} kip).")
                suggested_spacing = 0.0
            else:
                if Vs_req > 0.0:
                    s_strength = av * self.fy_shear * effective_depth / Vs_req
                else:
                    s_strength = float("inf")
                fy_shear_psi = self.fy_shear * 1000.0
                denom = max(0.75 * math.sqrt(fc_psi), 50.0) * b
                s_min_reinforcement = av * fy_shear_psi / denom
                limit_4_sqrt = (4.0 * math.sqrt(fc_psi) * b * effective_depth) / 1000.0
                if Vs_req <= limit_4_sqrt:
                    s_max = min(effective_depth / 2.0, 24.0)
                else:
                    s_max = min(effective_depth / 4.0, 12.0)
                s_design = min(s_strength, s_min_reinforcement, s_max)
                suggested_spacing = math.floor(s_design * 2) / 2.0
                if suggested_spacing < 3.0:
                    suggested_spacing = 3.0
                    messages.append("Stirrup spacing rounded down to absolute minimum practical limit of 3.0 inches.")

        return BeamDesignResult(
            required_flexure_As=required_As,
            suggested_bars=suggested_bars,
            provided_flexure_As=provided_As,
            required_shear_spacing=suggested_spacing,
            stirrup_bar_size=self.stirrup_bar_size,
            stirrup_legs=self.stirrup_legs,
            status=status,
            messages=messages,
        )