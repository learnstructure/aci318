"""
Material validators for ACI 318 limits.
"""

from aci318.utils.exceptions import MaterialValidationError


def validate_concrete_material(fc: float, wc: float = 0.145) -> None:
    """
    Validate concrete material properties according to ACI 318 limits.
    
    Args:
        fc: Specified compressive strength f'c in ksi.
        wc: Unit weight in kcf (default 0.145 kcf = 145 pcf).
        
    Raises:
        MaterialValidationError: If properties fall outside code limits.
    """
    if fc <= 0.0:
        raise MaterialValidationError(f"Concrete compressive strength f'c must be positive, got {fc} ksi.")
    if fc < 2.5:  # 2500 psi minimum structural concrete per ACI 318-19 Table 19.2.1.1
        raise MaterialValidationError(
            f"Concrete f'c={fc:.2f} ksi is below ACI 318 minimum structural concrete strength of 2.5 ksi (2500 psi)."
        )
    if fc > 20.0:
        raise MaterialValidationError(
            f"Concrete f'c={fc:.2f} ksi exceeds maximum supported strength limit of 20.0 ksi."
        )
    if wc <= 0.0 or wc > 0.25:
        raise MaterialValidationError(f"Concrete unit weight wc={wc} kcf is outside realistic limits (0.09 to 0.25 kcf).")


def validate_steel_material(fy: float, Es: float = 29000.0) -> None:
    """
    Validate steel reinforcement material properties according to ACI 318 limits.
    
    Args:
        fy: Specified yield strength fy in ksi.
        Es: Elastic modulus Es in ksi.
        
    Raises:
        MaterialValidationError: If properties fall outside code limits.
    """
    if fy <= 0.0:
        raise MaterialValidationError(f"Steel yield strength fy must be positive, got {fy} ksi.")
    if fy < 40.0:  # Grade 40 minimum
        raise MaterialValidationError(f"Steel fy={fy} ksi is below ACI 318 minimum grade limit of 40 ksi.")
    if fy > 100.0:  # ACI 318-19 §20.2.2.4 allows up to 100 ksi
        raise MaterialValidationError(f"Steel fy={fy} ksi exceeds ACI 318-19 maximum allowed yield strength limit of 100 ksi.")
    if Es <= 0.0:
        raise MaterialValidationError(f"Steel elastic modulus Es must be positive, got {Es} ksi.")
