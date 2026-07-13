from dataclasses import dataclass

@dataclass
class Steel:
    """
    Represents a steel reinforcement material.
    All properties stored in internal unit system (ksi, inches, kips).
    """
    fy: float                  # Yield strength of steel (ksi), e.g. 60.0
    Es: float = 29000.0        # Elastic modulus of steel (ksi) (default 29000.0 ksi)
    density: float = 490.0     # Density of steel in pcf (default 490.0 pcf)

    def __post_init__(self) -> None:
        if self.fy <= 0:
            raise ValueError("Steel yield strength fy must be positive.")
        if self.Es <= 0:
            raise ValueError("Steel elastic modulus Es must be positive.")

    @property
    def yield_strain(self) -> float:
        """
        Get yield strain of steel (epsilon_y = fy / Es).
        """
        return self.fy / self.Es
