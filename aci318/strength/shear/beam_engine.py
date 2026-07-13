import math
from typing import Tuple
from aci318.codes.base import DesignCode
from aci318.sections.rectangle import RectangleSection
from aci318.results.shear import ShearResult

def design_rectangular_beam_shear(
    section: RectangleSection,
    code: DesignCode,
    av: float = 0.22,         # Area of shear reinforcement (e.g. 2 legs of #3 stirrups = 2 * 0.11 = 0.22 in^2)
    s: float = 12.0,           # Spacing of stirrups (in)
    fy_shear: float = 60.0    # Yield strength of shear steel (ksi)
) -> ShearResult:
    """
    Computes nominal and design shear capacity of a rectangular concrete beam.
    Uses ACI 318 simplified method: Vc = 2 * lambda * sqrt(f'c) * b * d
    
    Args:
        section: RectangleSection section.
        code: DesignCode version implementation.
        av: Provided area of shear stirrups within distance s (in^2).
        s: Longitudinal spacing of stirrups (in).
        fy_shear: Yield strength of shear reinforcement (ksi).
        
    Returns:
        ShearResult containing shear capacity details.
    """
    b = section.b
    fc = section.concrete.fc
    
    # Get total tension steel to calculate d
    As, d = section.tension_steel
    if d == 0.0:
        d = section.h - 2.5 # approximation if no steel is placed
        
    # Get lambda factor
    lambda_val = code.get_lambda_(section.concrete)
    
    # Vc in lb: 2 * lambda * sqrt(f'c_psi) * b * d
    # fc is in ksi, so f'c_psi = fc * 1000
    fc_psi = fc * 1000.0
    vc_lb = 2.0 * lambda_val * math.sqrt(fc_psi) * b * d
    vc = vc_lb / 1000.0  # convert to kips
    
    # Vs in kips: Av * fy * d / s
    if s > 0 and av > 0:
        vs = av * fy_shear * d / s
    else:
        vs = 0.0
        
    vn = vc + vs
    phi = code.get_phi_shear()
    phi_vn = phi * vn
    
    status = "Passed"
    messages = []
    
    # Maximum Vs allowed (ACI 318 Section 22.5.1.2)
    vs_max = 8.0 * math.sqrt(fc_psi) * b * d / 1000.0
    if vs > vs_max:
        status = "Failed"
        messages.append(f"Nominal shear strength provided by stirrups Vs ({vs:.3f} kip) exceeds maximum allowed Vs_max ({vs_max:.3f} kip).")

    return ShearResult(
        vn_concrete=vc,
        vn_steel=vs,
        phi_vn=phi_vn,
        required_spacing=s,
        status=status,
        messages=messages
    )
