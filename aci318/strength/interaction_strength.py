from aci318.loads.load_effects import LoadEffects
from aci318.results.interaction import InteractionResult
from aci318.strength.base import StrengthChecker
from aci318.strength.axial_strength import AxialStrength
from aci318.strength.flexure_strength import FlexureStrength


class InteractionStrength(StrengthChecker):
    """Simple interaction strength checker for combined axial and flexural demand."""

    def check(self, loads: LoadEffects) -> InteractionResult:
        axial_result = AxialStrength(self.section, self.code).check(loads)
        flexure_result = FlexureStrength(self.section, self.code).check(loads)

        axial_ratio = loads.Pu / axial_result.phi_pn_max if axial_result.phi_pn_max > 0.0 else 0.0
        flexure_ratio = loads.Mu / flexure_result.phi_mn if flexure_result.phi_mn > 0.0 else 0.0
        combined_ratio = max(axial_ratio, flexure_ratio)

        status = "Passed"
        messages = []
        if combined_ratio > 1.0:
            status = "Failed"
            messages.append(f"Interaction demand/capacity ratio {combined_ratio:.2f} exceeds 1.0.")
        elif combined_ratio > 0.9:
            status = "Warning"
            messages.append(f"Interaction demand/capacity ratio {combined_ratio:.2f} is near capacity.")

        return InteractionResult(
            axial_ratio=axial_ratio,
            flexure_ratio=flexure_ratio,
            demand_capacity_ratio=combined_ratio,
            status=status,
            messages=messages,
        )
