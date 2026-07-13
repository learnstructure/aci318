from aci318.codes.base import DesignCode
from aci318.sections.rectangle import RectangleSection
from aci318.results.axial import AxialResult

def calculate_axial_capacity(
    section: RectangleSection,
    code: DesignCode,
    spiral: bool = False
) -> AxialResult:
    """
    Computes nominal and design axial capacity (tension/compression limits) of a column.
    Assumes tied column by default.
    """
    Ag = section.gross_area
    fc = section.concrete.fc
    
    # Sum all rebar layers
    Ast = sum(layer.area for layer in section.layers)
    
    if not section.layers:
        return AxialResult(
            pn_nominal=0.0,
            phi_pn=0.0,
            pn_max=0.0,
            phi_pn_max=0.0,
            status="Failed",
            messages=["No steel reinforcement provided."]
        )
        
    # Assume first layer steel is typical for fy
    fy = section.layers[0].steel.fy
    
    # Pure nominal axial capacity at zero eccentricity (Pn0)
    # Pn0 = 0.85 * f'c * (Ag - Ast) + fy * Ast
    pn0 = 0.85 * fc * (Ag - Ast) + fy * Ast
    
    # Reduction factors (tied = 0.65, spiral = 0.75)
    phi = code.get_phi_axial(compression=True, spiral=spiral)
    phi_pn = phi * pn0
    
    # Maximum nominal/design capacity including accidental eccentricity factor (0.80 for tied, 0.85 for spiral)
    ecc_factor = 0.85 if spiral else 0.80
    pn_max = ecc_factor * pn0
    phi_pn_max = ecc_factor * phi_pn
    
    status = "Passed"
    messages = []
    
    # Validate reinforcement ratio: 1% <= Ast/Ag <= 8% (ACI 318 Section 10.6.1.1)
    rho_g = Ast / Ag
    if rho_g < 0.01:
        status = "Warning"
        messages.append(f"Steel ratio rho_g ({rho_g:.4f}) is less than ACI minimum 0.01.")
    elif rho_g > 0.08:
        status = "Warning"
        messages.append(f"Steel ratio rho_g ({rho_g:.4f}) exceeds ACI maximum 0.08.")
        
    return AxialResult(
        pn_nominal=pn0,
        phi_pn=phi_pn,
        pn_max=pn_max,
        phi_pn_max=phi_pn_max,
        status=status,
        messages=messages
    )
