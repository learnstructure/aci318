import math
from aci318.loads.load_effects import LoadEffects
from aci318.results.torsion import TorsionResult
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class TorsionStrength(StrengthChecker):
    """
    Modular torsion strength checker for reinforced concrete members (ACI 318-19 Chapter 22 & Chapter 9).
    
    References:
        - ACI 318-19 §22.7: Torsional Strength
        - ACI 318-19 §9.6.4: Minimum Torsion Reinforcement
        - ACI 318-19 §22.7.7.1: Cross-Sectional Dimension Limits for Torsion
    """

    def __init__(self, section, code, fyt: float = 60.0) -> None:
        super().__init__(section, code)
        self.fyt = fyt

    def check(self, loads: LoadEffects) -> TorsionResult:
        """
        Perform torsional design check for given factored loads.
        
        Args:
            loads: LoadEffects object containing Tu (kip-in), Vu (kip), Pu (kip).
            
        Returns:
            TorsionResult dataclass.
        """
        validate_load_effects(loads)

        Tu = abs(loads.Tu)
        Vu = abs(loads.Vu)
        Pu = loads.Pu

        b = getattr(self.section, "b_w", getattr(self.section, "b", 12.0))
        h = self.section.h
        fc = self.section.concrete.fc
        fc_psi = fc * 1000.0

        cover = 1.5
        stirrup_db = 0.375
        fy = 60.0
        fyt = self.fyt

        if self.section.layers:
            fy = self.section.layers[-1].steel.fy

        Acp = b * h
        pcp = 2.0 * b + 2.0 * h

        b_core = max(b - 2.0 * (cover + stirrup_db / 2.0), 1.0)
        h_core = max(h - 2.0 * (cover + stirrup_db / 2.0), 1.0)
        Aoh = b_core * h_core
        Ao = 0.85 * Aoh
        ph = 2.0 * b_core + 2.0 * h_core

        lambda_val = self.code.get_lambda_(self.section.concrete)
        phi_t = self.code.get_phi_torsion()

        t_th = self.code.get_threshold_torsion(fc, Acp, pcp, Pu, Acp, lambda_val)
        t_cr = self.code.get_cracking_torsion(fc, Acp, pcp, Pu, Acp, lambda_val)
        phi_t_th = phi_t * t_th

        messages = []
        status = "Passed"

        # ACI 318-19 §22.7.1.1: Torsion effects can be neglected if Tu <= phi * Tth
        if Tu <= phi_t_th:
            messages.append(
                f"Factored torsion Tu={Tu:.2f} kip-in is <= phi * threshold torsion phi*Tth={phi_t_th:.2f} kip-in "
                f"(Tth={t_th:.2f} kip-in). Torsion effects can be neglected."
            )
            return TorsionResult(
                tn_nominal=0.0,
                phi_tn=0.0,
                required_transverse_steel=0.0,
                required_longitudinal_steel=0.0,
                threshold_torsion=t_th,
                cracking_torsion=t_cr,
                status="Passed",
                messages=messages,
                demand_capacity_ratio=Tu / phi_t_th if phi_t_th > 0 else 0.0,
            )

        # Cross-sectional dimension limit check (§22.7.7.1)
        # sqrt((Vu / (bw * d))^2 + (Tu * ph / (1.7 * Aoh^2))^2) <= phi * (Vc / (bw * d) + 8 * sqrt(f'c))
        d = self.section.tension_steel[1] if self.section.tension_steel[1] > 0.0 else h - 2.5
        vu_psi = (Vu * 1000.0) / (b * d)
        tu_psi_in = (Tu * 1000.0)
        torsion_stress_psi = (tu_psi_in * ph) / (1.7 * (Aoh ** 2))
        combined_stress = math.sqrt(vu_psi ** 2 + torsion_stress_psi ** 2)

        # For cross-sectional limits with stirrups (ACI 318 §22.7.7.1), Vc/(bw*d) = 2*lambda*sqrt(f'c)
        vc_psi = 2.0 * lambda_val * math.sqrt(fc_psi)
        max_allowed_stress = phi_t * (vc_psi + 8.0 * math.sqrt(fc_psi))

        if combined_stress > max_allowed_stress:
            status = "Failed"
            messages.append(
                f"Cross-sectional dimensions inadequate for combined shear and torsion: stress {combined_stress:.1f} psi > max allowed {max_allowed_stress:.1f} psi. Increase section dimensions."
            )

        # Required transverse torsion steel At/s (per leg, in^2/in)
        # Tu <= phi * 2 * Ao * (At/s) * fyt
        at_over_s = (Tu * 1000.0) / (2.0 * phi_t * Ao * fyt * 1000.0)

        # Minimum transverse steel (2 legs of stirrup: Av + 2*At)
        denom = max(fyt * 1000.0, 1.0)
        min_transverse_rate = max(0.75 * math.sqrt(fc_psi), 50.0) * b / denom
        at_over_s_design = max(at_over_s, min_transverse_rate / 2.0)

        # Required longitudinal steel Al (in^2) (§22.7.6.1 & §9.6.4.3)
        al_req = at_over_s_design * ph * (fyt / fy)
        at_over_s_for_min = max(at_over_s_design, (25.0 * b) / denom)
        al_min = (5.0 * math.sqrt(fc_psi) * Acp) / (fy * 1000.0) - at_over_s_for_min * ph * (fyt / fy)
        al_design = max(al_req, max(al_min, 0.0))

        nominal_Tn = (2.0 * Ao * at_over_s_design * fyt * 1000.0) / 1000.0  # in kip-in
        phi_Tn = phi_t * nominal_Tn

        ratio = Tu / phi_Tn if phi_Tn > 0.0 else 0.0
        if ratio > 1.0:
            status = "Failed"
            messages.append(f"Torsional demand/capacity ratio {ratio:.2f} exceeds 1.0.")

        return TorsionResult(
            tn_nominal=nominal_Tn,
            phi_tn=phi_Tn,
            required_transverse_steel=at_over_s_design,
            required_longitudinal_steel=al_design,
            threshold_torsion=t_th,
            cracking_torsion=t_cr,
            status=status,
            messages=messages,
            demand_capacity_ratio=ratio,
        )
