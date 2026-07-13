"""
Unit conversion utilities for the aci318 package.
The internal unit system is:
- Force: kip
- Length: inch
- Stress: ksi
- Moment: kip-in
"""

# Length conversion factors
IN_TO_MM = 25.4
MM_TO_IN = 1.0 / IN_TO_MM

IN_TO_FT = 1.0 / 12.0
FT_TO_IN = 12.0

IN_TO_M = 0.0254
M_TO_IN = 1.0 / IN_TO_M

# Force conversion factors
KIP_TO_LB = 1000.0
LB_TO_KIP = 0.001

KIP_TO_KN = 4.4482216152605
KN_TO_KIP = 1.0 / KIP_TO_KN

KIP_TO_N = 4448.2216152605
N_TO_KIP = 1.0 / KIP_TO_N

# Stress / Pressure conversion factors
KSI_TO_PSI = 1000.0
PSI_TO_KSI = 0.001

KSI_TO_MPA = 6.894757293168361
MPA_TO_KSI = 1.0 / KSI_TO_MPA

KSI_TO_KSF = 144.0
KSF_TO_KSI = 1.0 / 144.0

KSI_TO_PSF = 144000.0
PSF_TO_KSI = 1.0 / 144000.0

# Moment conversion factors
KIPIN_TO_KIPFT = 1.0 / 12.0
KIPFT_TO_KIPIN = 12.0

KIPIN_TO_KNM = 0.1129848290276167
KNM_TO_KIPIN = 1.0 / KIPIN_TO_KNM

KIPIN_TO_NMM = 112984.8290276167
NMM_TO_KIPIN = 1.0 / KIPIN_TO_NMM


def convert_force(value: float, unit_from: str, unit_to: str) -> float:
    """Convert force between different units."""
    # Convert to kip first
    unit_from = unit_from.lower()
    unit_to = unit_to.lower()
    
    if unit_from == "kip":
        val_kip = value
    elif unit_from in ("lb", "lbs"):
        val_kip = value * LB_TO_KIP
    elif unit_from == "kn":
        val_kip = value * KN_TO_KIP
    elif unit_from == "n":
        val_kip = value * N_TO_KIP
    else:
        raise ValueError(f"Unknown force unit: {unit_from}")
        
    # Convert from kip to target unit
    if unit_to == "kip":
        return val_kip
    elif unit_to in ("lb", "lbs"):
        return val_kip * KIP_TO_LB
    elif unit_to == "kn":
        return val_kip * KIP_TO_KN
    elif unit_to == "n":
        return val_kip * KIP_TO_N
    else:
        raise ValueError(f"Unknown force unit: {unit_to}")


def convert_length(value: float, unit_from: str, unit_to: str) -> float:
    """Convert length between different units."""
    unit_from = unit_from.lower()
    unit_to = unit_to.lower()
    
    # Convert to inch first
    if unit_from in ("in", "inch", "inches"):
        val_in = value
    elif unit_from in ("ft", "foot", "feet"):
        val_in = value * FT_TO_IN
    elif unit_from == "mm":
        val_in = value * MM_TO_IN
    elif unit_from == "m":
        val_in = value * M_TO_IN
    else:
        raise ValueError(f"Unknown length unit: {unit_from}")
        
    # Convert from inch to target unit
    if unit_to in ("in", "inch", "inches"):
        return val_in
    elif unit_to in ("ft", "foot", "feet"):
        return val_in * IN_TO_FT
    elif unit_to == "mm":
        return val_in * IN_TO_MM
    elif unit_to == "m":
        return val_in * IN_TO_M
    else:
        raise ValueError(f"Unknown length unit: {unit_to}")


def convert_stress(value: float, unit_from: str, unit_to: str) -> float:
    """Convert stress/pressure between different units."""
    unit_from = unit_from.lower()
    unit_to = unit_to.lower()
    
    # Convert to ksi first
    if unit_from == "ksi":
        val_ksi = value
    elif unit_from == "psi":
        val_ksi = value * PSI_TO_KSI
    elif unit_from == "mpa":
        val_ksi = value * MPA_TO_KSI
    elif unit_from == "ksf":
        val_ksi = value * KSF_TO_KSI
    elif unit_from == "psf":
        val_ksi = value * PSF_TO_KSI
    else:
        raise ValueError(f"Unknown stress unit: {unit_from}")
        
    # Convert from ksi to target unit
    if unit_to == "ksi":
        return val_ksi
    elif unit_to == "psi":
        return val_ksi * KSI_TO_PSI
    elif unit_to == "mpa":
        return val_ksi * KSI_TO_MPA
    elif unit_to == "ksf":
        return val_ksi * KSI_TO_KSF
    elif unit_to == "psf":
        return val_ksi * KSI_TO_PSF
    else:
        raise ValueError(f"Unknown stress unit: {unit_to}")


def convert_moment(value: float, unit_from: str, unit_to: str) -> float:
    """Convert moment between different units."""
    unit_from = unit_from.lower()
    unit_to = unit_to.lower()
    
    # Convert to kip-in first
    if unit_from in ("kip-in", "kipin"):
        val_kipin = value
    elif unit_from in ("kip-ft", "kipft"):
        val_kipin = value * KIPFT_TO_KIPIN
    elif unit_from in ("kn-m", "knm"):
        val_kipin = value * KNM_TO_KIPIN
    elif unit_from in ("n-mm", "nmm"):
        val_kipin = value * NMM_TO_KIPIN
    else:
        raise ValueError(f"Unknown moment unit: {unit_from}")
        
    # Convert from kip-in to target unit
    if unit_to in ("kip-in", "kipin"):
        return val_kipin
    elif unit_to in ("kip-ft", "kipft"):
        return val_kipin * KIPIN_TO_KIPFT
    elif unit_to in ("kn-m", "knm"):
        return val_kipin * KIPIN_TO_KNM
    elif unit_to in ("n-mm", "nmm"):
        return val_kipin * KIPIN_TO_NMM
    else:
        raise ValueError(f"Unknown moment unit: {unit_to}")
