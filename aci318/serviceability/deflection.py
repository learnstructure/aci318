import math
from aci318.sections.rectangle import RectangleSection

def calculate_cracking_moment(section: RectangleSection, yt: float) -> float:
    """
    Computes cracking moment (Mcr) in kip-in.
    Mcr = fr * Ig / yt
    fr = 7.5 * lambda * sqrt(f'c) in psi (modulus of rupture, ACI 318-19 Section 19.2.3)
    """
    fc = section.concrete.fc
    ig = section.gross_inertia
    fr_psi = 7.5 * 1.0 * math.sqrt(fc * 1000.0) # Assume lambda = 1.0 for cracking
    fr = fr_psi / 1000.0 # Convert to ksi
    return fr * ig / yt


def calculate_effective_inertia(
    section: RectangleSection,
    ma: float,                  # Service bending moment (kip-in)
    icr: float                  # Cracked moment of inertia (in^4)
) -> float:
    """
    Computes effective moment of inertia (Ie) in in^4 according to ACI 318-19 Section 24.2.3.5.
    Ie = Icr / (1 - (Mcr/Ma)^2 * (1 - Icr/Ig))
    """
    ig = section.gross_inertia
    yt = section.centroid
    mcr = calculate_cracking_moment(section, yt)
    
    if ma <= mcr:
        return ig
        
    ie = icr / (1.0 - ((mcr / ma) ** 2) * (1.0 - icr / ig))
    return min(ie, ig)
