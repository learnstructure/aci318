import math
from typing import Any
from aci318.codes.aci318_19 import ACI318_19


class ACI318_25(ACI318_19):
    """
    Concrete implementation of ACI 318-25 design code provisions.
    Inherits from ACI318_19 with provisions updated for ACI 318-25 code revisions.
    
    Key Revisions in ACI 318-25:
        - Section 25.4.3.1: Restored linear formula for standard hook development length ldh
          with reinforcement size factor psi_s, cover factor psi_cc, and confining factor psi_r.
        - Section 21.2.2: Accommodates high-strength reinforcement (Grade 80, Grade 100) with
          epsilon_ty = fy / Es and tension-controlled limit epsilon_tc = epsilon_ty + 0.003.
        - Section 21.2.2.3: Limit on phi for nonprestressed members under combined moment and
          axial compression between 0.10*f'c*Ag and Pn,bal.
    
    References:
        ACI CODE-318-25: Building Code Requirements for Structural Concrete and Commentary.
    """


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
        Strength reduction factor for combined moment and axial force (ACI 318-25 §21.2.2).

        Per §21.2.2.3, for nonprestressed members with 0.10 f'c Ag <= Pn <= Pn,bal, phi from
        Table 21.2.2 shall not exceed the linear interpolation between 0.90 at 0.10 f'c Ag and
        phi_cc (0.65 tied, 0.75 spiral) at Pn,bal.
        """
        phi = self.get_phi_flexure(strain_t, spiral=spiral, fy=fy)
        if pn_bal > pn_low and pn_low <= pn <= pn_bal:
            phi_cc = 0.75 if spiral else 0.65
            phi_cap = 0.90 - (0.90 - phi_cc) * (pn - pn_low) / (pn_bal - pn_low)
            phi = min(phi, phi_cap)
        return phi

    def get_reinforcement_grade_factor(self, fy: float) -> float:
        """
        Get reinforcement grade factor psi_g for straight tension development length (ACI 318-25 Table 25.4.2.5).
        
        Args:
            fy: Steel yield strength in ksi.
            
        Returns:
            float: psi_g factor (1.0 for Grade 40/60, 1.15 for Grade 80, 1.30 for Grade 100).
        """
        if fy >= 95.0:
            return 1.30
        elif fy >= 75.0:
            return 1.15
        return 1.0
