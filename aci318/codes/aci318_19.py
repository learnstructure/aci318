import math
from typing import Any
from aci318.codes.base import DesignCode


class ACI318_19(DesignCode):
    """
    Concrete implementation of ACI 318-19 design code provisions.
    All internal calculations assume inputs in ksi / inches / kips.
    
    References:
        ACI 318-19: Building Code Requirements for Structural Concrete.
    """

    def get_phi_flexure(self, strain_t: float, spiral: bool = False, fy: float = 60.0) -> float:
        """
        Get strength reduction factor (phi) for flexure (ACI 318-19 Table 21.2.2).
        
        Equation:
            For Grade 60: epsilon_ty = 0.002.
            For other grades: epsilon_ty = fy / Es (ACI 318-19 §21.2.2.1).
            Tension-controlled limit: epsilon_tc = epsilon_ty + 0.003.
            Tension-controlled (strain_t >= epsilon_tc): phi = 0.90
            Compression-controlled (strain_t <= epsilon_ty): phi = 0.65 (tied) or 0.75 (spiral)
            Transition: phi = phi_min + (strain_t - epsilon_ty) * (0.90 - phi_min) / (epsilon_tc - epsilon_ty)
            
        Args:
            strain_t: Net tensile strain in extreme tension steel.
            spiral: True if member has spiral reinforcement.
            fy: Steel yield strength in ksi (default 60.0).
            
        Returns:
            float: Strength reduction factor phi.
        """
        epsilon_ty = self.get_epsilon_ty(fy)
        epsilon_tc = self.get_tension_controlled_strain(fy)
        phi_min = 0.75 if spiral else 0.65
        phi_max = 0.90

        if strain_t <= epsilon_ty:
            return phi_min
        elif strain_t >= epsilon_tc:
            return phi_max
        else:
            return phi_min + (strain_t - epsilon_ty) * (phi_max - phi_min) / (epsilon_tc - epsilon_ty)

    def get_epsilon_ty(self, fy: float = 60.0) -> float:
        """
        Yield strain of deformed reinforcement (§21.2.2.1): fy / Es, permitted as 0.002 for Grade 60.

        Args:
            fy: Steel yield strength in ksi.
        """
        return 0.002 if abs(fy - 60.0) < 1e-3 else fy / 29000.0

    def get_tension_controlled_strain(self, fy: float = 60.0) -> float:
        """
        Net tensile strain limit for tension-controlled sections, epsilon_ty + 0.003 (Table 21.2.2).

        Args:
            fy: Steel yield strength in ksi.
        """
        return self.get_epsilon_ty(fy) + 0.003

    def get_phi_axial_flexure(
        self,
        strain_t: float,
        pn: float,
        pn_low: float,
        pn_bal: float,
        spiral: bool = False,
        fy: float = 60.0,
    ) -> float:
        """
        Strength reduction factor for combined moment and axial force (§21.2.2).

        ACI 318-19 determines phi from the net tensile strain only.

        Args:
            strain_t: Net tensile strain in the extreme tension steel.
            pn: Nominal axial strength at the evaluated point (kip, compression positive).
            pn_low: 0.10 * f'c * Ag (kip).
            pn_bal: Nominal axial strength at the balanced strain condition (kip).
            spiral: True if member has spiral reinforcement.
            fy: Steel yield strength in ksi.
        """
        return self.get_phi_flexure(strain_t, spiral=spiral, fy=fy)

    def get_phi_shear(self) -> float:
        """
        Get strength reduction factor (phi) for shear (ACI 318-19 Table 21.2.1).
        
        Returns:
            float: 0.75
        """
        return 0.75

    def get_phi_torsion(self) -> float:
        """
        Get strength reduction factor (phi) for torsion (ACI 318-19 Table 21.2.1).
        
        Returns:
            float: 0.75
        """
        return 0.75

    def get_phi_axial(self, compression: bool, spiral: bool = False) -> float:
        """
        Get strength reduction factor (phi) for axial strength (ACI 318-19 Table 21.2.1).
        
        Args:
            compression: True if compression-controlled, False if tension-controlled.
            spiral: True if spiral reinforcement used.
            
        Returns:
            float: Strength reduction factor.
        """
        if compression:
            return 0.75 if spiral else 0.65
        else:
            return 0.90

    def get_beta_1(self, f_c: float) -> float:
        """
        Get beta_1 factor for equivalent rectangular concrete stress block (ACI 318-19 Table 22.2.2.4.3).
        
        Equation:
            For f_c <= 4.0 ksi: beta_1 = 0.85
            For 4.0 < f_c < 8.0 ksi: beta_1 = 0.85 - 0.05 * (f_c - 4.0)
            For f_c >= 8.0 ksi: beta_1 = 0.65
            
        Args:
            f_c: Concrete compressive strength in ksi.
            
        Returns:
            float: beta_1 factor (bounded between 0.65 and 0.85).
        """
        if f_c <= 4.0:
            return 0.85
        elif f_c >= 8.0:
            return 0.65
        else:
            return 0.85 - 0.05 * (f_c - 4.0)

    def get_lambda_(self, concrete: Any) -> float:
        """
        Get lightweight concrete modification factor lambda (ACI 318-19/-25 §19.2.4).

        - Normalweight concrete: lambda = 1.0 (§19.2.4.3).
        - 'sand-lightweight' / 'all-lightweight': by aggregate composition, Table 19.2.4.1(b)
          (0.85 / 0.75).
        - 'lightweight': by equilibrium density w_c [pcf], Table 19.2.4.1(a):
          w_c <= 100: 0.75;  100 < w_c <= 135: 0.0075 w_c <= 1.0;  w_c > 135: 1.0.

        Args:
            concrete: Concrete material object (``concrete_type`` and ``density`` in pcf).

        Returns:
            float: lambda modification factor.
        """
        ct = str(concrete.concrete_type).lower().replace("_", "-")
        if ct == "normalweight":
            return 1.0
        if "sand" in ct:
            return 0.85
        if "all" in ct:
            return 0.75
        if ct == "lightweight":
            w_c = float(concrete.density)
            if w_c <= 100.0:
                return 0.75
            return min(0.0075 * w_c, 1.0)
        raise ValueError(
            f"Unknown concrete_type '{concrete.concrete_type}'. Use 'normalweight', 'sand-lightweight', "
            "'all-lightweight', or 'lightweight' (lambda from equilibrium density, Table 19.2.4.1(a))."
        )

    def get_minimum_steel_ratio(self, f_c: float = 4.0, f_y: float = 60.0) -> float:
        """
        Get minimum flexural reinforcement ratio (ACI 318-19 §9.6.1.2).
        
        Equation:
            rho_min = max(3 * sqrt(f_c_psi) / f_y_psi, 200 / f_y_psi)
            
        Args:
            f_c: Concrete compressive strength in ksi.
            f_y: Steel yield strength in ksi.
            
        Returns:
            float: Minimum steel ratio.
        """
        f_c_psi = f_c * 1000.0
        f_y_psi = min(f_y, 80.0) * 1000.0  # fy limited to 80,000 psi (§9.6.1.2)
        return max(3.0 * math.sqrt(f_c_psi) / f_y_psi, 200.0 / f_y_psi)

    def get_vc(
        self,
        f_c: float,
        b_w: float,
        d: float,
        N_u: float = 0.0,
        A_g: float = 1.0,
        A_v: float = 0.0,
        A_v_min: float = 0.0,
        lambda_val: float = 1.0,
        rho_w: float = 0.01,
    ) -> float:
        """
        Get concrete shear strength Vc in kips (ACI 318-19 Table 22.5.5.1).
        
        Equations:
            When Av >= Av_min:
                Vc = [2 * lambda * sqrt(f'c) + Nu / (6 * Ag)] * bw * d / 1000
            When Av < Av_min (size effect factor applies):
                lambda_s = sqrt(2 / (1 + d / 10)) <= 1.0
                Vc = [8 * lambda_s * lambda * (rho_w)^(1/3) * sqrt(f'c) + Nu / (6 * Ag)] * bw * d / 1000
                
        Args:
            f_c: Concrete compressive strength in ksi.
            b_w: Web width in inches.
            d: Effective depth in inches.
            N_u: Factored axial force in kips (positive for compression).
            A_g: Gross concrete area in sq inches.
            A_v: Provided shear reinforcement area in sq inches.
            A_v_min: Minimum shear reinforcement area in sq inches.
            lambda_val: Lightweight concrete factor.
            rho_w: Longitudinal reinforcement ratio As / (bw * d).
            
        Returns:
            float: Nominal concrete shear strength Vc in kips.
        """
        f_c_psi = f_c * 1000.0
        # ACI 318-19 §22.5.5.1.2: Nu / (6 * Ag) shall not exceed 0.05 * f'c
        if N_u != 0.0:
            raw_axial = (N_u * 1000.0) / (6.0 * max(A_g, 1.0))
            if raw_axial > 0.0:
                axial_term = min(raw_axial, 0.05 * f_c_psi)
            else:
                axial_term = raw_axial
        else:
            axial_term = 0.0

        if A_v >= A_v_min and A_v > 0.0:
            vc_psi = (2.0 * lambda_val * math.sqrt(f_c_psi) + axial_term)
        else:
            lambda_s = min(math.sqrt(2.0 / (1.0 + d / 10.0)), 1.0)
            rho_term = max(rho_w, 0.001) ** (1.0 / 3.0)
            vc_psi = (8.0 * lambda_s * lambda_val * rho_term * math.sqrt(f_c_psi) + axial_term)

        Vc = (vc_psi * b_w * d) / 1000.0

        # ACI 318-19 §22.5.5.1.1: Upper limit Vc <= 5.0 * lambda * sqrt(f'c) * bw * d
        vc_max = (5.0 * lambda_val * math.sqrt(f_c_psi) * b_w * d) / 1000.0
        Vc = min(Vc, vc_max)

        return max(Vc, 0.0)

    def get_threshold_torsion(
        self,
        f_c: float,
        Acp: float,
        pcp: float,
        N_u: float = 0.0,
        A_g: float = 1.0,
        lambda_val: float = 1.0,
    ) -> float:
        """
        Get threshold torsion Tth in kip-in (ACI 318-19 Table 22.7.4.1).
        
        Equation:
            Tth = lambda * sqrt(f'c) * (Acp^2 / pcp) * sqrt(1 + Nu / (4 * Ag * lambda * sqrt(f'c))) / 1000
            
        Args:
            f_c: Concrete compressive strength in ksi.
            Acp: Area enclosed by outside perimeter of section in sq inches.
            pcp: Outside perimeter of concrete cross section in inches.
            N_u: Factored axial load in kips (compression positive).
            A_g: Gross area of concrete in sq inches.
            lambda_val: Lightweight concrete factor.
            
        Returns:
            float: Threshold torsion Tth in kip-inches (nominal, without phi).
        """
        f_c_psi = f_c * 1000.0
        sqrt_fc = math.sqrt(f_c_psi)

        axial_factor = 1.0
        if N_u != 0.0 and A_g > 0.0:
            nu_psi = (N_u * 1000.0) / A_g
            denom = 4.0 * lambda_val * sqrt_fc
            if denom > 0.0:
                val = 1.0 + nu_psi / denom
                axial_factor = math.sqrt(max(val, 0.0))

        t_th_lbs_in = lambda_val * sqrt_fc * (Acp ** 2 / max(pcp, 1.0)) * axial_factor
        return t_th_lbs_in / 1000.0

    def get_cracking_torsion(
        self,
        f_c: float,
        Acp: float,
        pcp: float,
        N_u: float = 0.0,
        A_g: float = 1.0,
        lambda_val: float = 1.0,
    ) -> float:
        """
        Get cracking torsion Tcr in kip-in (ACI 318-19 §22.7.5.1).
        
        Equation:
            Tcr = 4 * lambda * sqrt(f'c) * (Acp^2 / pcp) * sqrt(1 + Nu / (4 * Ag * lambda * sqrt(f'c))) / 1000
            
        Returns:
            float: Cracking torsion Tcr in kip-inches.
        """
        f_c_psi = f_c * 1000.0
        sqrt_fc = math.sqrt(f_c_psi)

        axial_factor = 1.0
        if N_u != 0.0 and A_g > 0.0:
            nu_psi = (N_u * 1000.0) / A_g
            denom = 4.0 * lambda_val * sqrt_fc
            if denom > 0.0:
                val = 1.0 + nu_psi / denom
                axial_factor = math.sqrt(max(val, 0.0))

        t_cr_lbs_in = 4.0 * lambda_val * sqrt_fc * (Acp ** 2 / max(pcp, 1.0)) * axial_factor
        return t_cr_lbs_in / 1000.0

    def get_reinforcement_grade_factor(self, fy: float) -> float:
        """Reinforcement grade factor psi_g (ACI 318-19 Table 25.4.3.2)."""
        if fy <= 60.0 + 1e-3:
            return 1.0
        elif fy <= 80.0 + 1e-3:
            return 1.15
        else:
            return 1.30

    def get_hook_development_length(
        self,
        db: float,
        fy: float,
        fc: float,
        lambda_val: float = 1.0,
        is_epoxy: bool = False,
        confined: bool = False,
        in_column_core: bool = False,
        **kwargs: Any,
    ) -> float:
        """
        Get standard 90/180-degree hook development length ldh in inches (ACI 318-19 §25.4.3.1, Eq. 25.4.3.1a).
        
        Equation:
            ldh = [fy * psi_e * psi_r * psi_o * psi_c * psi_g / (55 * lambda * sqrt(f'c))] * db^1.5
            not less than max(8 * db, 6.0 in).
        """
        fc_psi = fc * 1000.0
        fy_psi = fy * 1000.0
        psi_e = 1.2 if is_epoxy else 1.0
        psi_r = 1.0 if confined else 1.6
        psi_o = 1.0 if in_column_core else 1.25
        psi_c = min(fc_psi / 15000.0 + 0.6, 1.0)
        psi_g = self.get_reinforcement_grade_factor(fy)

        denom = 55.0 * max(lambda_val, 0.5) * math.sqrt(fc_psi)
        ldh = (fy_psi * psi_e * psi_r * psi_o * psi_c * psi_g / denom) * (db ** 1.5)
        return max(ldh, 8.0 * db, 6.0)

