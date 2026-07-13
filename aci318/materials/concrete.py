import math
from dataclasses import dataclass, field

@dataclass
class Concrete:
    """
    Represents a concrete material.
    All properties stored in internal unit system (ksi, inches, kips).
    """
    fc: float                  # Concrete compressive strength (ksi), e.g. 4.0
    density: float = 145.0     # Density of concrete in pcf (default 145.0 pcf for normal weight)
    concrete_type: str = "normalweight" # e.g. "normalweight", "sand-lightweight", "all-lightweight"
    max_strain: float = 0.003  # Maximum usable compressive strain (ACI 318-19 Section 22.2.2.1)
    _Ec: float = field(default=0.0, init=False) # Elastic modulus (ksi)

    def __post_init__(self) -> None:
        # Validate properties
        if self.fc <= 0:
            raise ValueError("Concrete compressive strength fc must be positive.")
        if self.density <= 0:
            raise ValueError("Concrete density must be positive.")

    @property
    def Ec(self) -> float:
        """
        Get elastic modulus of concrete (Ec) in ksi.
        If not explicitly overridden, it is calculated per ACI 318-19 Section 19.2.2:
        Ec = 33 * (w_c^1.5) * sqrt(f'_c) in psi, or Ec = 57000 * sqrt(f'_c) for normal weight.
        """
        if self._Ec > 0.0:
            return self._Ec
            
        # Calculation in psi: w_c in pcf, f'_c in psi
        fc_psi = self.fc * 1000.0
        
        if self.concrete_type.lower() == "normalweight":
            ec_psi = 57000.0 * math.sqrt(fc_psi)
        elif 90.0 <= self.density <= 160.0:
            ec_psi = 33.0 * (self.density ** 1.5) * math.sqrt(fc_psi)
        else:
            ec_psi = 57000.0 * math.sqrt(fc_psi)
            
        return ec_psi / 1000.0  # Convert to ksi

    @Ec.setter
    def Ec(self, value: float) -> None:
        if value <= 0:
            raise ValueError("Elastic modulus must be positive.")
        self._Ec = value
