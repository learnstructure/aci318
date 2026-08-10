from aci318.codes.aci318_19 import ACI318_19


class ACI318_25(ACI318_19):
    """
    Concrete implementation of ACI 318-25 design code provisions.
    Inherits from ACI318_19 with provisions updated for ACI 318-25 code revisions.
    
    References:
        ACI 318-25: Building Code Requirements for Structural Concrete.
    """

    def get_minimum_steel_ratio(self, f_c: float = 4.0, f_y: float = 60.0) -> float:
        """
        Get minimum flexural reinforcement ratio according to ACI 318-25.
        Allows high-strength steel grades up to 100 ksi.
        
        Args:
            f_c: Concrete compressive strength in ksi.
            f_y: Steel yield strength in ksi.
            
        Returns:
            float: Minimum steel ratio.
        """
        return super().get_minimum_steel_ratio(f_c=f_c, f_y=f_y)
