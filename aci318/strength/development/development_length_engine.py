"""
Development length calculation engine according to ACI 318.
"""
import math
from typing import Any, List, Optional
from struct_core import AppliedDefault
from aci318.codes.base import DesignCode
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.development import DevelopmentResult

def calculate_development_length(
    bar_diameter: float,
    steel: Steel,
    concrete: Concrete,
    code: DesignCode,
    is_top_bar: bool = False,
    is_epoxy: bool = False,
    is_lightweight: bool = False,
    confined: Optional[bool] = None,
    in_column_core: Optional[bool] = None,
    clear_spacing: Optional[float] = None,
    cover: Optional[float] = None,
    min_transverse: bool = False,
) -> DevelopmentResult:
    """
    Computes required development length for tension and compression rebar.
    Assumes standard ACI 318 factors:
    ld = (fy * psi_t * psi_e * psi_s / (20 * lambda * sqrt(f'c))) * db for smaller bars.
    """
    fc_psi = concrete.fc * 1000.0
    fy_psi = steel.fy * 1000.0
    db = bar_diameter
    
    # Factors (ACI 318 Section 25.4.2.4 & Table 25.4.2.5)
    psi_t = 1.3 if is_top_bar else 1.0
    psi_e = 1.2 if is_epoxy else 1.0
    psi_te = min(psi_t * psi_e, 1.7)
    psi_s = 0.8 if db <= 0.75 else 1.0  # size factor for #6 and smaller bars
    psi_g = getattr(code, "get_reinforcement_grade_factor", lambda fy: 1.15 if fy >= 75.0 else 1.0)(steel.fy)
    lambda_val = code.get_lambda_(concrete)
    
    # Tension development length ld (ACI 318 Section 25.4.2)
    # Base equation (favourable row of Table 25.4.2.3):
    ld_tension = (fy_psi * psi_te * psi_s * psi_g) / (20.0 * lambda_val * math.sqrt(fc_psi)) * db

    # Table 25.4.2.3: 1.5x when spacing/cover conditions are not met
    if clear_spacing is not None and cover is not None:
        favourable = (
            (clear_spacing >= db and cover >= db and min_transverse)
            or (clear_spacing >= 2.0 * db and cover >= db)
        )
        if not favourable:
            ld_tension *= 1.5
    
    # Compression development length ldc (ACI 318 Section 25.4.9)
    # ldc is the greater of: (0.02 * fy * db / (lambda * sqrt(f'c))) and (0.0003 * fy * db)
    ldc1 = (0.02 * fy_psi * db) / (lambda_val * math.sqrt(fc_psi))
    ldc2 = 0.0003 * fy_psi * db
    ld_compression = max(ldc1, ldc2, 8.0)  # minimum 8 inches per ACI 318
    
    # Tension development hook ldh (ACI 318 Section 25.4.3)
    defaults_applied: List[AppliedDefault] = []
    actual_confined = confined if confined is not None else False
    if confined is None:
        defaults_applied.append(
            AppliedDefault(
                name="hook_confined",
                value=False,
                unit=None,
                source="ACI 318-19 §25.4.3.2 (unconfined conservative default psi_r=1.6)",
                applies_to=f"Bar dia {bar_diameter} in",
            )
        )
    actual_in_column_core = in_column_core if in_column_core is not None else False
    if in_column_core is None:
        defaults_applied.append(
            AppliedDefault(
                name="hook_in_column_core",
                value=False,
                unit=None,
                source="ACI 318-19 §25.4.3.2 (outside column core conservative default psi_o=1.25)",
                applies_to=f"Bar dia {bar_diameter} in",
            )
        )

    if hasattr(code, "get_hook_development_length"):
        ldh_hook = code.get_hook_development_length(
            db=db,
            fy=steel.fy,
            fc=concrete.fc,
            lambda_val=lambda_val,
            is_epoxy=is_epoxy,
            confined=actual_confined,
            in_column_core=actual_in_column_core,
        )
    else:
        ldh = (0.02 * psi_e * fy_psi * db) / (max(lambda_val, 0.5) * math.sqrt(fc_psi))
        ldh_hook = max(ldh, 8.0 * db, 6.0)
    
    return DevelopmentResult(
        ld_tension=max(ld_tension, 12.0), # minimum 12 inches tension development length
        ld_compression=ld_compression,
        ldh_hook=ldh_hook,
        splice_length=1.3 * max(ld_tension, 12.0), # Class B splice default
        status="Passed",
        defaults_applied=defaults_applied,
    )
