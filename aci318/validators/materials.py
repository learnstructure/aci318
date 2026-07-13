"""
Material property validators.
"""

def validate_concrete_strength(fc: float) -> None:
    """Validate concrete compressive strength fc."""
    if fc <= 0.0:
        raise ValueError(f"Concrete compressive strength must be positive, got {fc}")
    if fc < 2.5:
        # ACI 318-19 Section 19.2.1.1 minimum fc is typically 2500 psi (2.5 ksi) for structural concrete
        import warnings
        warnings.warn(f"Concrete strength {fc} ksi is below ACI 318 typical minimum of 2.5 ksi.")


def validate_steel_yield(fy: float) -> None:
    """Validate steel yield strength fy."""
    if fy <= 0.0:
        raise ValueError(f"Steel yield strength must be positive, got {fy}")
    if fy > 100.0:
        # ACI 318 limits fy to 100 ksi for reinforcement in most applications
        import warnings
        warnings.warn(f"Steel yield strength {fy} ksi exceeds ACI 318 limit of 100 ksi.")
