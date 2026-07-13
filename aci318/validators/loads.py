"""
Load validation functions.
"""
from typing import Any

def validate_load_effects(load_effects: Any) -> None:
    """Validate that load effects is a valid LoadEffects object."""
    # Check that required attributes are present
    required_attrs = ["Pu", "Mu", "Vu", "Tu"]
    for attr in required_attrs:
        if not hasattr(load_effects, attr):
            raise TypeError(f"Load effects object must have a '{attr}' attribute.")
        val = getattr(load_effects, attr)
        if not isinstance(val, (int, float)):
            raise TypeError(f"Load effect '{attr}' must be numeric, got {type(val)}")
