import math

from aci318.loads.load_effects import LoadEffects
from aci318.results.flexure import FlexureResult
from aci318.strength.base import StrengthChecker


class FlexureStrength(StrengthChecker):
    """Modular flexural strength checker for reinforced concrete members."""

    def check(self, loads: LoadEffects) -> FlexureResult:
        b = self.section.b
        h = self.section.h
        fc = self.section.concrete.fc
        beta_1 = self.code.get_beta_1(fc)
        epsilon_cu = self.section.concrete.max_strain

        As, d = self.section.tension_steel
        if As <= 0.0 or d <= 0.0:
            result = FlexureResult(
                required_steel=0.0,
                provided_steel=0.0,
                neutral_axis=0.0,
                steel_strain=0.0,
                phi_mn=0.0,
                status="Failed",
                messages=["No tension steel provided in section."],
            )
            result.demand_capacity_ratio = 0.0
            return result

        fy = self.section.layers[-1].steel.fy
        Es = self.section.layers[-1].steel.Es
        epsilon_ty = fy / Es

        T = As * fy
        a = T / (0.85 * fc * b)
        c = a / beta_1
        strain_t = epsilon_cu * (d - c) / c

        if strain_t < epsilon_ty:
            A_coef = 0.85 * fc * b * beta_1
            B_coef = Es * As * epsilon_cu
            C_coef = -Es * As * epsilon_cu * d
            c = (-B_coef + math.sqrt(B_coef**2 - 4 * A_coef * C_coef)) / (2 * A_coef)
            a = beta_1 * c
            strain_t = epsilon_cu * (d - c) / c
            fs = Es * strain_t
            T = As * fs

        mn = T * (d - a / 2.0)
        phi = self.code.get_phi_flexure(strain_t)
        phi_mn = phi * mn

        status = "Passed"
        messages = []
        min_steel_ratio = self.code.get_minimum_steel_ratio(fc, fy)
        min_As = min_steel_ratio * b * d
        if As < min_As:
            status = "Warning"
            messages.append(f"Tension reinforcement As ({As:.3f} in^2) is less than ACI minimum As_min ({min_As:.3f} in^2).")
        if strain_t < 0.004:
            status = "Warning"
            messages.append(f"Net tensile strain strain_t ({strain_t:.5f}) is less than 0.004 (ductility warning).")

        result = FlexureResult(
            required_steel=min_As,
            provided_steel=As,
            neutral_axis=c,
            steel_strain=strain_t,
            phi_mn=phi_mn,
            status=status,
            messages=messages,
        )

        demand = max(loads.Mu, 0.0)
        capacity = max(result.phi_mn, 0.0)
        ratio = demand / capacity if capacity > 0.0 else 0.0

        if ratio > 1.0:
            result.status = "Failed"
            result.messages.append(f"Demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        elif ratio > 0.9:
            result.status = "Warning"
            result.messages.append(f"Demand/capacity ratio {ratio:.2f} is near capacity.")

        result.demand_capacity_ratio = ratio
        return result
