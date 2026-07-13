"""
Custom exception classes for aci318.
"""

class ACI318Error(Exception):
    """Base exception for all aci318 errors."""
    pass


class MaterialValidationError(ACI318Error):
    """Raised when material parameters do not comply with ACI 318 limits."""
    pass


class GeometryValidationError(ACI318Error):
    """Raised when section dimensions are invalid or violate limits."""
    pass


class ReinforcementValidationError(ACI318Error):
    """Raised when rebar configuration violates detailing or spacing rules."""
    pass
