from dataclasses import dataclass

@dataclass
class LoadEffects:
    """
    Standardized input contract for load actions on a structural member.
    All forces must be in the internal unit system (kip, inches).
    """
    Pu: float = 0.0   # Axial load (kip, compression positive)
    Mu: float = 0.0   # Bending moment (kip-in)
    Vu: float = 0.0   # Shear force (kip)
    Tu: float = 0.0   # Torsional moment (kip-in)
    
    # Future expansions:
    # Mu2: float = 0.0  # Biaxial bending moment about secondary axis (kip-in)
    # Vu2: float = 0.0  # Shear force in secondary direction (kip)
