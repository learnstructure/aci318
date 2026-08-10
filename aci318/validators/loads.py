"""
Validators for load effects and design actions.
"""

from aci318.loads.load_effects import LoadEffects
from aci318.utils.exceptions import ACI318Error


def validate_load_effects(loads: LoadEffects) -> None:
    """
    Validate load effects dataclass inputs.
    
    Args:
        loads: LoadEffects instance containing Pu, Mu, Vu, Tu.
        
    Raises:
        ACI318Error: If load inputs contain NaN or infinite values.
    """
    import math

    for name, val in [("Pu", loads.Pu), ("Mu", loads.Mu), ("Vu", loads.Vu), ("Tu", loads.Tu)]:
        if math.isnan(val) or math.isinf(val):
            raise ACI318Error(f"Load effect {name} contains invalid numeric value: {val}")
