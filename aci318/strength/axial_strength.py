from aci318.loads.load_effects import LoadEffects
from aci318.results.axial import AxialResult
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class AxialStrength(StrengthChecker):
    """
    Modular axial strength checker for compression members according to ACI 318-19 §22.4.
    
    Equations:
        Nominal Axial Compressive Strength Po (ACI 318-19 §22.4.2.2):
            Po = 0.85 * f'c * (Ag - Ast) + fy * Ast
            
        Maximum Nominal Axial Capacity Pn,max (ACI 318-19 Table 22.4.2.1):
            Pn,max = 0.80 * Po  (for tied columns)
            Pn,max = 0.85 * Po  (for spiral columns)
            
        Design Axial Capacity phi_Pn,max:
            phi_Pn,max = phi * Pn,max
            (where phi = 0.65 for tied columns, phi = 0.75 for spiral columns)
    """

    def __init__(self, section, code, spiral: bool = False) -> None:
        super().__init__(section, code)
        self.spiral = spiral

    def check(self, loads: LoadEffects) -> AxialResult:
        """
        Perform axial compressive strength check for given load effects.
        
        Args:
            loads: LoadEffects instance containing Pu (kip).
            
        Returns:
            AxialResult dataclass.
        """
        validate_load_effects(loads)

        Ag = self.section.gross_area
        fc = self.section.concrete.fc
        Ast = sum(layer.area for layer in self.section.layers)

        if not self.section.layers or Ast <= 0.0:
            return AxialResult(
                pn_nominal=0.0,
                phi_pn=0.0,
                pn_max=0.0,
                phi_pn_max=0.0,
                status="Failed",
                messages=["No steel reinforcement provided in column section."],
                demand_capacity_ratio=0.0,
            )

        fy = min(self.section.layers[0].steel.fy, 80.0)  # fy limited to 80 ksi (§22.4.2.1)
        pn0 = 0.85 * fc * (Ag - Ast) + fy * Ast
        phi = self.code.get_phi_axial(compression=True, spiral=self.spiral)
        phi_pn0 = phi * pn0

        ecc_factor = 0.85 if self.spiral else 0.80
        pn_max = ecc_factor * pn0
        phi_pn_max = ecc_factor * phi_pn0

        status = "Passed"
        messages = []
        rho_g = Ast / Ag

        if rho_g < 0.01:
            status = "Warning"
            messages.append(f"Longitudinal steel ratio rho_g ({rho_g:.4f}) is less than ACI 318 minimum 0.01.")
        elif rho_g > 0.08:
            status = "Warning"
            messages.append(f"Longitudinal steel ratio rho_g ({rho_g:.4f}) exceeds ACI 318 maximum 0.08.")

        demand = max(loads.Pu, 0.0)
        capacity = max(phi_pn_max, 0.0)
        ratio = demand / capacity if capacity > 0.0 else 0.0

        if ratio > 1.0:
            status = "Failed"
            messages.append(f"Axial demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        elif ratio > 0.9:
            status = "Warning"
            messages.append(f"Axial demand/capacity ratio {ratio:.2f} is near capacity.")

        return AxialResult(
            pn_nominal=pn0,
            phi_pn=phi_pn0,
            pn_max=pn_max,
            phi_pn_max=phi_pn_max,
            status=status,
            messages=messages,
            demand_capacity_ratio=ratio,
        )
