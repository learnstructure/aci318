"""
Deflection calculation engine according to ACI 318-19 Section 24.2.
Computes cracking moment (Mcr), cracked transformed moment of inertia (Icr),
effective moment of inertia (Ie per Eq. 24.2.3.5a), time-dependent long-term multiplier
(lambda_delta per Section 24.2.4.1), and immediate / long-term beam deflections.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Union
from aci318.sections.rectangle import RectangleSection
from aci318.sections.tbeam import TBeamSection


def calculate_cracking_moment(
    section: Union[RectangleSection, TBeamSection],
    yt: Optional[float] = None,
    lambda_val: float = 1.0,
) -> float:
    """
    Computes cracking moment (Mcr) in kip-in according to ACI 318-19 Section 24.2.3.5.
    
    Equations:
        fr = 7.5 * lambda * sqrt(f'c)  [psi] (ACI 318-19 Section 19.2.3.1)
        Mcr = fr * Ig / yt            [kip-in]
    """
    fc = section.concrete.fc
    ig = section.gross_inertia
    h = section.h

    if yt is None:
        c = getattr(section, "centroid", h / 2.0)
        yt = max(h - c, 0.1)

    fr_psi = 7.5 * lambda_val * math.sqrt(fc * 1000.0)
    fr = fr_psi / 1000.0  # Convert to ksi
    return (fr * ig) / max(yt, 0.1)


def calculate_cracked_inertia(
    section: Union[RectangleSection, TBeamSection],
    n_ratio: Optional[float] = None,
) -> float:
    """
    Computes cracked transformed moment of inertia (Icr) in in^4 for a reinforced concrete section.
    
    Solves for the cracked elastic neutral axis kd from first moment of area of transformed section:
        b * (kd)^2 / 2 + (n - 1) * As' * (kd - d') = n * As * (d - kd)
    and then computes:
        Icr = b * (kd)^3 / 3 + n * As * (d - kd)^2 + (n - 1) * As' * (kd - d')^2
    """
    fc = section.concrete.fc
    fc_psi = fc * 1000.0
    h = section.h
    is_tbeam = isinstance(section, TBeamSection)
    bw = getattr(section, "b_w", getattr(section, "b", 12.0))
    bf = getattr(section, "b_f", getattr(section, "b", bw)) if is_tbeam else bw
    hf = getattr(section, "h_f", 0.0) if is_tbeam else 0.0

    # Modular ratio n = Es / Ec
    if n_ratio is None:
        ec_ksi = getattr(section.concrete, "Ec", None)
        if ec_ksi is None or ec_ksi <= 0.0:
            ec_ksi = (57000.0 * math.sqrt(fc_psi)) / 1000.0
        es_ksi = getattr(section.layers[0].steel, "Es", 29000.0) if getattr(section, "layers", None) else 29000.0
        n = es_ksi / max(ec_ksi, 100.0)
    else:
        n = float(n_ratio)

    as_tens, d_tens = section.tension_steel
    if as_tens <= 0.0 or d_tens <= 0.0:
        d_tens = max(h - 2.5, 1.0)
        as_tens = 0.01 * bw * d_tens

    as_comp, d_comp = getattr(section, "compression_steel", (0.0, 0.0))
    n_minus_1 = max(n - 1.0, 0.0)

    # First, test if neutral axis falls within flange (kd <= hf) or rectangular section:
    b_effective = bf if is_tbeam else bw
    A = b_effective / 2.0
    B = n * as_tens + n_minus_1 * as_comp
    C = - (n * as_tens * d_tens + n_minus_1 * as_comp * d_comp)

    disc = B ** 2 - 4.0 * A * C
    kd = (-B + math.sqrt(max(disc, 0.0))) / (2.0 * A) if disc >= 0.0 else 0.35 * d_tens

    if is_tbeam and hf > 0.0 and kd > hf:
        # Neutral axis falls below the flange into web:
        A_t = bw / 2.0
        B_t = (bf - bw) * hf + n * as_tens + n_minus_1 * as_comp
        C_t = - (0.5 * (bf - bw) * (hf ** 2) + n * as_tens * d_tens + n_minus_1 * as_comp * d_comp)
        disc_t = B_t ** 2 - 4.0 * A_t * C_t
        if disc_t >= 0.0:
            kd = (-B_t + math.sqrt(disc_t)) / (2.0 * A_t)

        kd = min(max(kd, 0.05 * d_tens), d_tens)
        icr_conc = (bw * (kd ** 3)) / 3.0 + ((bf - bw) * (hf ** 3)) / 12.0 + (bf - bw) * hf * ((kd - hf / 2.0) ** 2)
    else:
        kd = min(max(kd, 0.05 * d_tens), d_tens)
        icr_conc = (b_effective * (kd ** 3)) / 3.0

    # Cracked moment of inertia
    icr_tens = n * as_tens * ((d_tens - kd) ** 2)
    icr_comp = n_minus_1 * as_comp * (((kd - d_comp) ** 2) if kd > d_comp else 0.0)

    icr = icr_conc + icr_tens + icr_comp
    return max(icr, 0.01)


def calculate_effective_inertia(
    section: Union[RectangleSection, TBeamSection],
    ma: float,                            # Service bending moment (kip-in)
    icr: Optional[float] = None,          # Cracked moment of inertia (in^4, computed if None)
    lambda_val: float = 1.0,
) -> float:
    """
    Computes effective moment of inertia (Ie) in in^4 according to ACI 318-19 Section 24.2.3.5.
    
    Provisions (ACI 318-19 Table 24.2.3.5):
        For Ma <= (2/3) * Mcr:
            Ie = Ig
        For Ma > (2/3) * Mcr:
            Ie = Icr / [ 1 - (( (2/3)*Mcr / Ma )^2) * ( 1 - Icr / Ig ) ] <= Ig
    """
    ig = section.gross_inertia
    h = section.h
    yt = getattr(section, "centroid", h / 2.0)
    yt_tension = max(h - yt, 0.1)

    mcr = calculate_cracking_moment(section, yt=yt_tension, lambda_val=lambda_val)

    if icr is None or icr <= 0.0:
        icr = calculate_cracked_inertia(section)

    ma_abs = abs(ma)
    two_thirds_mcr = (2.0 / 3.0) * mcr

    if ma_abs <= two_thirds_mcr or ma_abs <= 1e-4:
        return ig

    ratio = (two_thirds_mcr / ma_abs) ** 2
    denom = 1.0 - ratio * (1.0 - (icr / max(ig, 1.0)))

    if denom <= 0.0:
        return min(icr, ig)

    ie = icr / denom
    return min(max(ie, icr), ig)


def calculate_long_term_factor(
    sustained_months: float = 60.0,
    rho_prime: float = 0.0,
) -> float:
    """
    Computes time-dependent factor lambda_delta for sustained load deflections
    according to ACI 318-19 Section 24.2.4.1.1:
        lambda_delta = xi / (1 + 50 * rho')
    
    where xi:
        - 3 months:  1.0
        - 6 months:  1.2
        - 12 months: 1.4
        - 60+ months (5+ years): 2.0
    """
    if sustained_months <= 3.0:
        xi = 1.0
    elif sustained_months <= 6.0:
        xi = 1.0 + (sustained_months - 3.0) * (1.2 - 1.0) / 3.0
    elif sustained_months <= 12.0:
        xi = 1.2 + (sustained_months - 6.0) * (1.4 - 1.2) / 6.0
    elif sustained_months < 60.0:
        xi = 1.4 + (sustained_months - 12.0) * (2.0 - 1.4) / 48.0
    else:
        xi = 2.0

    return xi / (1.0 + 50.0 * max(rho_prime, 0.0))


@dataclass
class BeamDeflectionResult:
    """Summary dataclass of beam deflection serviceability evaluation."""
    span_in: float
    m_cr: float
    i_g: float
    i_cr: float
    i_e: float
    immediate_dead_deflection: float
    immediate_live_deflection: float
    long_term_deflection: float
    total_deflection: float
    limit_l_over_360: float
    limit_l_over_240: float
    passed: bool
    status: str
    messages: list[str]


def calculate_beam_deflection(
    span_in: float,
    section: Union[RectangleSection, TBeamSection],
    w_dead_kip_per_in: float,
    w_live_kip_per_in: float,
    support_condition: str = "simple",
    sustained_live_ratio: float = 0.0,
    sustained_months: float = 60.0,
) -> BeamDeflectionResult:
    """
    Evaluates immediate and long-term deflections of a beam according to ACI 318-19 §24.2.
    
    Supports:
        - "simple" (5 * w * L^4 / (384 * E * Ie))
        - "cantilever" (w * L^4 / (8 * E * Ie))
        - "fixed-fixed" (w * L^4 / (384 * E * Ie))
        - "propped-cantilever" (w * L^4 / (185 * E * Ie))
    """
    fc = section.concrete.fc
    ec_ksi = (57000.0 * math.sqrt(fc * 1000.0)) / 1000.0
    l_in = float(span_in)

    # Moments at midspan or support
    cond = support_condition.lower()
    if cond == "cantilever":
        coeff = 1.0 / 8.0
        m_coeff = 0.5
    elif cond in ("fixed", "fixed-fixed"):
        coeff = 1.0 / 384.0
        m_coeff = 1.0 / 24.0
    elif cond in ("propped", "propped-cantilever"):
        coeff = 1.0 / 185.0
        m_coeff = 9.0 / 128.0
    else:  # simple span
        coeff = 5.0 / 384.0
        m_coeff = 1.0 / 8.0

    w_d = w_dead_kip_per_in
    w_l = w_live_kip_per_in
    w_total = w_d + w_l

    m_d = m_coeff * w_d * (l_in ** 2)
    m_total = m_coeff * w_total * (l_in ** 2)

    ig = section.gross_inertia
    icr = calculate_cracked_inertia(section)
    mcr = calculate_cracking_moment(section)

    ie_d = calculate_effective_inertia(section, ma=m_d, icr=icr)
    ie_total = calculate_effective_inertia(section, ma=m_total, icr=icr)

    # Immediate deflections
    delta_d = (coeff * w_d * (l_in ** 4)) / max(ec_ksi * ie_d, 1e-4)
    delta_total_imm = (coeff * w_total * (l_in ** 4)) / max(ec_ksi * ie_total, 1e-4)
    delta_l = max(delta_total_imm - delta_d, 0.0)

    # Compression steel ratio rho'
    as_comp, d_comp = getattr(section, "compression_steel", (0.0, 0.0))
    as_tens, d_tens = section.tension_steel
    b = getattr(section, "b_w", getattr(section, "b", 12.0))
    rho_prime = as_comp / max(b * d_tens, 1.0) if d_tens > 0 else 0.0

    lambda_delta = calculate_long_term_factor(sustained_months=sustained_months, rho_prime=rho_prime)

    # Sustained load: 100% dead + sustained live fraction
    w_sust = w_d + sustained_live_ratio * w_l
    delta_sust = (coeff * w_sust * (l_in ** 4)) / max(ec_ksi * ie_total, 1e-4)
    delta_long_term = lambda_delta * delta_sust

    total_deflection = delta_d + delta_l + delta_long_term

    limit_360 = l_in / 360.0
    limit_240 = l_in / 240.0

    messages = []
    passed = True
    if delta_l > limit_360:
        passed = False
        messages.append(f"Immediate live load deflection ({delta_l:.3f} in) exceeds L/360 limit ({limit_360:.3f} in).")
    if total_deflection > limit_240:
        passed = False
        messages.append(f"Total long-term deflection ({total_deflection:.3f} in) exceeds L/240 limit ({limit_240:.3f} in).")

    return BeamDeflectionResult(
        span_in=l_in,
        m_cr=round(mcr, 2),
        i_g=round(ig, 1),
        i_cr=round(icr, 1),
        i_e=round(ie_total, 1),
        immediate_dead_deflection=round(delta_d, 4),
        immediate_live_deflection=round(delta_l, 4),
        long_term_deflection=round(delta_long_term, 4),
        total_deflection=round(total_deflection, 4),
        limit_l_over_360=round(limit_360, 4),
        limit_l_over_240=round(limit_240, 4),
        passed=passed,
        status="Passed" if passed else "Failed",
        messages=messages,
    )
