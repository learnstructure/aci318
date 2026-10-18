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

    def get_hook_development_length(
        self,
        db: float,
        fy: float,
        fc: float,
        lambda_val: float = 1.0,
        is_epoxy: bool = False,
        side_cover: float = 2.5,
        confined_by_ties: bool = False,
    ) -> float:
        """
        Get standard 90/180-degree hook development length ldh in inches according to ACI 318-25 §25.4.3.1.
        
        Equation (ACI 318-25 §25.4.3.1):
            ldh = (fy * psi_e * psi_s * psi_cc * psi_r) / (50 * lambda * sqrt(f'c)) * db
            not less than max(8 * db, 6.0 inches)
            
        Args:
            db: Nominal bar diameter in inches.
            fy: Steel yield strength in ksi.
            fc: Concrete compressive strength in ksi.
            lambda_val: Lightweight concrete modification factor (0.75 for lightweight, 1.0 for normal weight).
            is_epoxy: True if epoxy coated reinforcement (psi_e = 1.2).
            side_cover: Side clear cover normal to plane of hook in inches (psi_cc = 0.7 if >= 2.5 in).
            confined_by_ties: True if enclosed within ties/stirrups at s <= 3*db (psi_r = 0.8).
            
        Returns:
            float: Required hook development length ldh in inches.
        """
        fc_psi = fc * 1000.0
        fy_psi = fy * 1000.0

        # Epoxy factor psi_e (Table 25.4.3.2)
        psi_e = 1.2 if is_epoxy else 1.0

        # Reinforcement size factor psi_s (Table 25.4.3.2)
        if db <= 1.128:  # #9 bar (29 mm) and smaller
            psi_s = 1.0
        elif db <= 1.410:  # #10 and #11 bars (32 mm and 36 mm)
            psi_s = 1.15
        elif db <= 1.693:  # #14 bar (43 mm)
            psi_s = 1.30
        else:  # #18 bar (57 mm)
            psi_s = 1.50

        # Cover factor psi_cc (Table 25.4.3.2)
        psi_cc = 0.7 if side_cover >= 2.5 and db <= 1.410 else 1.0

        # Confining reinforcement factor psi_r (Table 25.4.3.2)
        psi_r = 0.8 if confined_by_ties and db <= 1.410 else 1.0

        denom = 50.0 * max(lambda_val, 0.5) * math.sqrt(fc_psi)
        ldh = (fy_psi * psi_e * psi_s * psi_cc * psi_r * db) / denom
        return max(ldh, 8.0 * db, 6.0)

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
