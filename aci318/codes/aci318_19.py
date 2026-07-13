from typing import Any
from aci318.codes.base import DesignCode

class ACI318_19(DesignCode):
    """
    Concrete implementation of ACI 318-19 design code provisions.
    Calculations assume inputs are in ksi/inches/kip.
    """

    def get_phi_flexure(self, strain_t: float, spiral: bool = False) -> float:
        """
        Get the strength reduction factor (phi) for flexure (ACI 318-19 Table 21.2.2).
        
        Args:
            strain_t: Net tensile strain in extreme tension steel.
            spiral: True if member has spiral reinforcement, False if tied.
            
        Returns:
            float: Strength reduction factor.
        """
        # Compression-controlled strain limit (typically 0.002 for Grade 60)
        epsilon_ty = 0.002
        # Tension-controlled strain limit (0.005 for ACI 318-19)
        epsilon_tc = 0.005
        
        phi_min = 0.75 if spiral else 0.65
        phi_max = 0.90
        
        if strain_t <= epsilon_ty:
            return phi_min
        elif strain_t >= epsilon_tc:
            return phi_max
        else:
            # Linear transition
            return phi_min + (strain_t - epsilon_ty) * (phi_max - phi_min) / (epsilon_tc - epsilon_ty)

    def get_phi_shear(self) -> float:
        """
        Get the strength reduction factor (phi) for shear (ACI 318-19 Table 21.2.1).
        
        Returns:
            float: 0.75
        """
        return 0.75

    def get_phi_axial(self, compression: bool, spiral: bool = False) -> float:
        """
        Get the strength reduction factor (phi) for axial strength.
        
        Args:
            compression: True if member is compression-controlled, False if tension-controlled.
            spiral: True if member has spiral reinforcement, False if tied.
            
        Returns:
            float: Strength reduction factor.
        """
        if compression:
            return 0.75 if spiral else 0.65
        else:
            return 0.90

    def get_beta_1(self, f_c: float) -> float:
        """
        Get the beta_1 factor (ACI 318-19 Table 22.2.2.4.3).
        
        Args:
            f_c: Concrete compressive strength in ksi.
            
        Returns:
            float: beta_1 factor.
        """
        # f_c is in ksi.
        if f_c <= 4.0:
            return 0.85
        elif f_c >= 8.0:
            return 0.65
        else:
            return 0.85 - 0.05 * (f_c - 4.0)

    def get_lambda_(self, concrete: Any) -> float:
        """
        Get lightweight concrete modification factor (lambda) (ACI 318-19 Section 19.2.4).
        
        Args:
            concrete: Concrete material object. Must have 'density' property (pcf)
                      or 'concrete_type' attribute.
                      
        Returns:
            float: lambda modification factor.
        """
        # If concrete object has concrete_type attribute
        if hasattr(concrete, "concrete_type"):
            ct = concrete.concrete_type.lower()
            if "lightweight" in ct:
                if "sand" in ct:
                    return 0.85
                return 0.75
        
        # Or check density
        if hasattr(concrete, "density"):
            w_c = concrete.density  # in pcf
            if w_c < 115.0:
                return 0.75
            elif w_c < 135.0:
                # Interpolation or simplified sand-lightweight
                return 0.85
        
        return 1.0

    def get_minimum_steel_ratio(self, f_c: float = 4.0, f_y: float = 60.0) -> float:
        """
        Get minimum flexural reinforcement ratio (ACI 318-19 Section 9.6.1.2).
        Min ratio = max(3 * sqrt(f'c) / fy, 200 / fy) where f'c and fy are in psi.
        
        Args:
            f_c: Concrete compressive strength in ksi.
            f_y: Steel yield strength in ksi.
            
        Returns:
            float: Minimum steel ratio.
        """
        f_c_psi = f_c * 1000.0
        f_y_psi = f_y * 1000.0
        import math
        val1 = 3.0 * math.sqrt(f_c_psi) / f_y_psi
        val2 = 200.0 / f_y_psi
        return max(val1, val2)
