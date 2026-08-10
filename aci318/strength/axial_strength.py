from aci318.loads.load_effects import LoadEffects
from aci318.results.axial import AxialResult
from aci318.strength.base import StrengthChecker


class AxialStrength(StrengthChecker):
    """Modular axial strength checker for reinforced concrete members."""

    def __init__(self, section, code, spiral: bool = False) -> None:
        super().__init__(section, code)
        self.spiral = spiral

    def check(self, loads: LoadEffects) -> AxialResult:
        Ag = self.section.gross_area
        fc = self.section.concrete.fc
        Ast = sum(layer.area for layer in self.section.layers)

        if not self.section.layers:
            result = AxialResult(
                pn_nominal=0.0,
                phi_pn=0.0,
                pn_max=0.0,
                phi_pn_max=0.0,
                status="Failed",
                messages=["No steel reinforcement provided."],
            )
            result.demand_capacity_ratio = 0.0
            return result

        fy = self.section.layers[0].steel.fy
        pn0 = 0.85 * fc * (Ag - Ast) + fy * Ast
        phi = self.code.get_phi_axial(compression=True, spiral=self.spiral)
        phi_pn = phi * pn0
        ecc_factor = 0.85 if self.spiral else 0.80
        pn_max = ecc_factor * pn0
        phi_pn_max = ecc_factor * phi_pn

        status = "Passed"
        messages = []
        rho_g = Ast / Ag
        if rho_g < 0.01:
            status = "Warning"
            messages.append(f"Steel ratio rho_g ({rho_g:.4f}) is less than ACI minimum 0.01.")
        elif rho_g > 0.08:
            status = "Warning"
            messages.append(f"Steel ratio rho_g ({rho_g:.4f}) exceeds ACI maximum 0.08.")

        result = AxialResult(
            pn_nominal=pn0,
            phi_pn=phi_pn,
            pn_max=pn_max,
            phi_pn_max=phi_pn_max,
            status=status,
            messages=messages,
        )

        demand = max(loads.Pu, 0.0)
        capacity = max(result.phi_pn_max, 0.0)
        ratio = demand / capacity if capacity > 0.0 else 0.0

        if ratio > 1.0:
            result.status = "Failed"
            result.messages.append(f"Demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        elif ratio > 0.9:
            result.status = "Warning"
            result.messages.append(f"Demand/capacity ratio {ratio:.2f} is near capacity.")

        result.demand_capacity_ratio = ratio
        return result
