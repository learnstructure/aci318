"""
Unit conversion utilities for aci318.
"""

# Exact conversion factors
MM_PER_INCH: float = 25.4
INCH_PER_MM: float = 1.0 / MM_PER_INCH

IN_TO_MM: float = MM_PER_INCH
MM_TO_IN: float = INCH_PER_MM

KN_PER_KIP: float = 4.4482216152605
KIP_PER_KN: float = 1.0 / KN_PER_KIP

MPA_PER_KSI: float = 6.894757293168361
KSI_PER_MPA: float = 1.0 / MPA_PER_KSI

PA_PER_PSI: float = 6894.757293168361
PSI_PER_MPA: float = 145.03773773020923

# Generic conversion dispatchers
def convert_length(val: float, from_unit: str, to_unit: str) -> float:
    from_u, to_u = from_unit.lower(), to_unit.lower()
    if from_u == to_u:
        return val
    if from_u in ("in", "inch", "inches"):
        in_val = val
    elif from_u in ("ft", "feet"):
        in_val = val * 12.0
    elif from_u in ("mm", "millimeter"):
        in_val = val * INCH_PER_MM
    elif from_u in ("m", "meter"):
        in_val = val * 1000.0 * INCH_PER_MM
    else:
        raise ValueError(f"Unknown length unit: {from_unit}")

    if to_u in ("in", "inch", "inches"):
        return in_val
    elif to_u in ("ft", "feet"):
        return in_val / 12.0
    elif to_u in ("mm", "millimeter"):
        return in_val * MM_PER_INCH
    elif to_u in ("m", "meter"):
        return (in_val * MM_PER_INCH) / 1000.0
    else:
        raise ValueError(f"Unknown length unit: {to_unit}")


def convert_force(val: float, from_unit: str, to_unit: str) -> float:
    from_u, to_u = from_unit.lower(), to_unit.lower()
    if from_u == to_u:
        return val
    if from_u in ("kip", "kips"):
        kip_val = val
    elif from_u in ("lb", "lbs", "pound"):
        kip_val = val / 1000.0
    elif from_u in ("kn", "kilonewton"):
        kip_val = val * KIP_PER_KN
    elif from_u in ("n", "newton"):
        kip_val = (val / 1000.0) * KIP_PER_KN
    else:
        raise ValueError(f"Unknown force unit: {from_unit}")

    if to_u in ("kip", "kips"):
        return kip_val
    elif to_u in ("lb", "lbs", "pound"):
        return kip_val * 1000.0
    elif to_u in ("kn", "kilonewton"):
        return kip_val * KN_PER_KIP
    elif to_u in ("n", "newton"):
        return kip_val * KN_PER_KIP * 1000.0
    else:
        raise ValueError(f"Unknown force unit: {to_unit}")


def convert_stress(val: float, from_unit: str, to_unit: str) -> float:
    from_u, to_u = from_unit.lower(), to_unit.lower()
    if from_u == to_u:
        return val
    if from_u in ("ksi",):
        ksi_val = val
    elif from_u in ("psi",):
        ksi_val = val / 1000.0
    elif from_u in ("mpa", "n/mm2"):
        ksi_val = val * KSI_PER_MPA
    elif from_u in ("pa", "n/m2"):
        ksi_val = (val / 1e6) * KSI_PER_MPA
    else:
        raise ValueError(f"Unknown stress unit: {from_unit}")

    if to_u in ("ksi",):
        return ksi_val
    elif to_u in ("psi",):
        return ksi_val * 1000.0
    elif to_u in ("mpa", "n/mm2"):
        return ksi_val * MPA_PER_KSI
    else:
        raise ValueError(f"Unknown stress unit: {to_unit}")


def convert_moment(val: float, from_unit: str, to_unit: str) -> float:
    from_u, to_u = from_unit.lower(), to_unit.lower()
    if from_u == to_u:
        return val
    if from_u in ("kip-in", "kipin"):
        kipin_val = val
    elif from_u in ("kip-ft", "kipft"):
        kipin_val = val * 12.0
    elif from_u in ("knm", "kn-m"):
        kipin_val = (val * 1000.0) / (KN_PER_KIP * MM_PER_INCH)
    else:
        raise ValueError(f"Unknown moment unit: {from_unit}")

    if to_u in ("kip-in", "kipin"):
        return kipin_val
    elif to_u in ("kip-ft", "kipft"):
        return kipin_val / 12.0
    elif to_u in ("knm", "kn-m"):
        return (kipin_val * KN_PER_KIP * MM_PER_INCH) / 1000.0
    else:
        raise ValueError(f"Unknown moment unit: {to_unit}")


# Specific helper functions
def inches_to_mm(inches: float) -> float:
    return inches * MM_PER_INCH

def mm_to_inches(mm: float) -> float:
    return mm * INCH_PER_MM

def feet_to_inches(feet: float) -> float:
    return feet * 12.0

def inches_to_feet(inches: float) -> float:
    return inches / 12.0

def kips_to_kn(kips: float) -> float:
    return kips * KN_PER_KIP

def kn_to_kips(kn: float) -> float:
    return kn * KIP_PER_KN

def lbs_to_kips(lbs: float) -> float:
    return lbs / 1000.0

def kips_to_lbs(kips: float) -> float:
    return kips * 1000.0

def ksi_to_mpa(ksi: float) -> float:
    return ksi * MPA_PER_KSI

def mpa_to_ksi(mpa: float) -> float:
    return mpa * KSI_PER_MPA

def psi_to_ksi(psi: float) -> float:
    return psi / 1000.0

def ksi_to_psi(ksi: float) -> float:
    return ksi * 1000.0

def mpa_to_psi(mpa: float) -> float:
    return mpa * PSI_PER_MPA

def psi_to_mpa(psi: float) -> float:
    return psi / PSI_PER_MPA

def kip_in_to_knm(kip_in: float) -> float:
    return (kip_in * KN_PER_KIP * MM_PER_INCH) / 1000.0

def knm_to_kip_in(knm: float) -> float:
    return (knm * 1000.0) / (KN_PER_KIP * MM_PER_INCH)

def kip_ft_to_kip_in(kip_ft: float) -> float:
    return kip_ft * 12.0

def kip_in_to_kip_ft(kip_in: float) -> float:
    return kip_in / 12.0

def sqin_to_sqmm(sqin: float) -> float:
    return sqin * (MM_PER_INCH ** 2)

def sqmm_to_sqin(sqmm: float) -> float:
    return sqmm * (INCH_PER_MM ** 2)
