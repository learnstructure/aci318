import math

from aci318.loads.load_effects import LoadEffects
from aci318.results.shear import ShearResult
from aci318.strength.base import StrengthChecker


class ShearStrength(StrengthChecker):
    """Modular shear strength checker for reinforced concrete members."""

    def __init__(self, section, code, av: float = 0.22, s: float = 12.0, fy_shear: float = 60.0) -> None:
        super().__init__(section, code)
        self.av = av
        self.s = s
        self.fy_shear = fy_shear

    def check(self, loads: LoadEffects) -> ShearResult:
        b = self.section.b
        fc = self.section.concrete.fc
        As, d = self.section.tension_steel
        if d == 0.0:
            d = self.section.h - 2.5

        lambda_val = self.code.get_lambda_(self.section.concrete)
        fc_psi = fc * 1000.0
        vc_lb = 2.0 * lambda_val * math.sqrt(fc_psi) * b * d
        vc = vc_lb / 1000.0

        if self.s > 0 and self.av > 0:
            vs = self.av * self.fy_shear * d / self.s
        else:
            vs = 0.0

        vn = vc + vs
        phi = self.code.get_phi_shear()
        phi_vn = phi * vn

        status = "Passed"
        messages = []
        vs_max = 8.0 * math.sqrt(fc_psi) * b * d / 1000.0
        if vs > vs_max:
            status = "Failed"
            messages.append(f"Nominal shear strength provided by stirrups Vs ({vs:.3f} kip) exceeds maximum allowed Vs_max ({vs_max:.3f} kip).")

        result = ShearResult(
            vn_concrete=vc,
            vn_steel=vs,
            phi_vn=phi_vn,
            required_spacing=self.s,
            status=status,
            messages=messages,
        )

        demand = max(loads.Vu, 0.0)
        capacity = max(result.phi_vn, 0.0)
        ratio = demand / capacity if capacity > 0.0 else 0.0

        if ratio > 1.0:
            result.status = "Failed"
            result.messages.append(f"Demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        elif ratio > 0.9:
            result.status = "Warning"
            result.messages.append(f"Demand/capacity ratio {ratio:.2f} is near capacity.")

        result.demand_capacity_ratio = ratio
        return result
