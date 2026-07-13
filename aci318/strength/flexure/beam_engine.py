from typing import Tuple
from aci318.codes.base import DesignCode
from aci318.sections.rectangle import RectangleSection
from aci318.results.flexure import FlexureResult

def design_rectangular_beam_flexure(
    section: RectangleSection, 
    code: DesignCode
) -> FlexureResult:
    """
    Computes flexural strength of a rectangular concrete section with tension reinforcement.
    Uses strain compatibility and standard equivalent rectangular stress block (Whitney).
    
    Args:
        section: RectangleSection containing dimensions, concrete, and steel rebar layers.
        code: DesignCode version implementation.
        
    Returns:
        FlexureResult containing capacity details.
    """
    b = section.b
    h = section.h
    fc = section.concrete.fc
    beta_1 = code.get_beta_1(fc)
    epsilon_cu = section.concrete.max_strain

    # Extract single equivalent tension reinforcement
    As, d = section.tension_steel
    
    if As <= 0.0 or d <= 0.0:
        return FlexureResult(
            required_steel=0.0,
            provided_steel=0.0,
            neutral_axis=0.0,
            steel_strain=0.0,
            phi_mn=0.0,
            status="Failed",
            messages=["No tension steel provided in section."]
        )

    # Assuming primary tension layer is steel[0].fy or generic steel
    fy = section.layers[-1].steel.fy
    Es = section.layers[-1].steel.Es
    epsilon_ty = fy / Es

    # First iteration: Assume tension steel yields (T = As * fy)
    T = As * fy
    a = T / (0.85 * fc * b)
    c = a / beta_1
    
    # Calculate strain in tension steel
    strain_t = epsilon_cu * (d - c) / c
    
    # If steel hasn't yielded, solve quadratic for neutral axis c:
    # 0.85 * fc * b * beta_1 * c^2 + Es * As * epsilon_cu * c - Es * As * epsilon_cu * d = 0
    if strain_t < epsilon_ty:
        # Solve quadratic: A c^2 + B c + C = 0
        A_coef = 0.85 * fc * b * beta_1
        B_coef = Es * As * epsilon_cu
        C_coef = -Es * As * epsilon_cu * d
        import math
        # Quadratic formula: (-B + sqrt(B^2 - 4AC)) / (2A)
        c = (-B_coef + math.sqrt(B_coef**2 - 4 * A_coef * C_coef)) / (2 * A_coef)
        a = beta_1 * c
        strain_t = epsilon_cu * (d - c) / c
        # Steel stress is Es * strain_t
        fs = Es * strain_t
        T = As * fs
        
    # Nominal moment capacity (Mn)
    mn = T * (d - a / 2.0)
    
    # Phi factor
    phi = code.get_phi_flexure(strain_t)
    phi_mn = phi * mn

    # Status checks
    status = "Passed"
    messages = []
    
    # Check minimum steel (ACI 318 Section 9.6.1.2)
    min_steel_ratio = code.get_minimum_steel_ratio(fc, fy)
    min_As = min_steel_ratio * b * d
    if As < min_As:
        status = "Warning"
        messages.append(f"Tension reinforcement As ({As:.3f} in^2) is less than ACI minimum As_min ({min_As:.3f} in^2).")

    # Check maximum reinforcement/ductility (typically net tensile strain >= 0.004 per ACI 318)
    if strain_t < 0.004:
        status = "Warning"
        messages.append(f"Net tensile strain strain_t ({strain_t:.5f}) is less than 0.004 (ductility warning).")

    return FlexureResult(
        required_steel=min_As,
        provided_steel=As,
        neutral_axis=c,
        steel_strain=strain_t,
        phi_mn=phi_mn,
        status=status,
        messages=messages
    )
