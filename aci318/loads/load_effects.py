from dataclasses import dataclass

@dataclass
class LoadEffects:
    """
    Standardized input contract for load actions on a structural member.
    All forces must be in the internal unit system (kip, inches).
    Supports uniaxial and biaxial bending moments (Mu2, Mu3) and shear forces (Vu2, Vu3).
    """
    Pu: float = 0.0    # Axial load (kip, compression positive)
    Mu: float = 0.0    # Bending moment about major axis (kip-in, alias for Mu2 or Mux)
    Vu: float = 0.0    # Shear force along major axis (kip, alias for Vu2)
    Tu: float = 0.0    # Torsional moment (kip-in)
    Mu2: float = 0.0   # Major axis bending moment (kip-in)
    Mu3: float = 0.0   # Minor axis bending moment (kip-in)
    Vu2: float = 0.0   # Major axis shear force (kip)
    Vu3: float = 0.0   # Minor axis shear force (kip)

    def __post_init__(self) -> None:
        # Synchronize Mu and Mu2
        if self.Mu != 0.0 and self.Mu2 == 0.0:
            self.Mu2 = self.Mu
        elif self.Mu2 != 0.0 and self.Mu == 0.0:
            self.Mu = self.Mu2

        # Synchronize Vu and Vu2
        if self.Vu != 0.0 and self.Vu2 == 0.0:
            self.Vu2 = self.Vu
        elif self.Vu2 != 0.0 and self.Vu == 0.0:
            self.Vu = self.Vu2
