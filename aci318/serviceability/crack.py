"""
Crack control verification according to ACI 318-19 Section 24.3.2.
Computes maximum allowable spacing of tension reinforcement to control flexural cracking
under service load conditions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Union
from aci318.sections.rectangle import RectangleSection
from aci318.sections.tbeam import TBeamSection


@dataclass
class CrackControlResult:
    """Results of crack control reinforcement spacing check."""
    allowable_spacing: float    # Maximum allowable bar spacing in inches
    provided_spacing: float     # Actual provided bar spacing in inches
    steel_stress_ksi: float     # Steel tensile stress fs at service load in ksi
    clear_cover_in: float       # Clear cover to tension reinforcement in inches
    passed: bool                # True if provided_spacing <= allowable_spacing
    status: str                 # "Passed" or "Failed"
    messages: list[str]


def _tension_fy(section) -> float:
    """fy of the section's tension bars (ksi); a section without bars gives no service stress to assume."""
    if not getattr(section, "layers", None):
        raise ValueError("Crack control needs the service steel stress fs or the section's tension bars (fy).")
    return section.layers[-1].steel.fy


def check_crack_control_spacing(
    section: Union[RectangleSection, TBeamSection],
    fs: Optional[float] = None, # Steel stress at service load (ksi). Defaults to (2/3)*fy per §24.3.2.1
    cc: float = 1.5,            # Clear cover to tension reinforcement (in)
) -> float:
    """
    Returns the maximum allowable spacing of tension reinforcement for crack control (in).
    
    Equation (ACI 318-19 Section 24.3.2):
        s_max = min( 15 * (40000 / fs) - 2.5 * cc,  12 * (40000 / fs) )
        where fs is in psi, cc is in inches.
    """
    if fs is None:
        # ACI 318-19 §24.3.2.1: fs may be taken as (2/3) * fy of the tension bars
        fs_calc = (2.0 / 3.0) * _tension_fy(section)
    else:
        fs_calc = float(fs)

    fs_psi = max(fs_calc * 1000.0, 1000.0)
    val1 = 15.0 * (40000.0 / fs_psi) - 2.5 * max(cc, 0.0)
    val2 = 12.0 * (40000.0 / fs_psi)
    return max(min(val1, val2), 1.0)


def verify_crack_control(
    section: Union[RectangleSection, TBeamSection],
    provided_spacing: float,
    fs: Optional[float] = None,
    ms_service_kip_in: Optional[float] = None,
    cc: float = 1.5,
) -> CrackControlResult:
    """
    Evaluates whether provided tension bar spacing satisfies ACI 318-19 §24.3.2 limits.
    
    If ms_service_kip_in is provided, estimates service steel stress:
        fs = Ms / (As * j * d)
    otherwise uses fs or defaults to (2/3) * fy.
    """
    as_tens, d_tens = section.tension_steel
    fy = _tension_fy(section)

    if fs is not None:
        fs_eval = float(fs)
    elif ms_service_kip_in is not None and as_tens > 0 and d_tens > 0:
        jd = 0.875 * d_tens
        fs_eval = min(ms_service_kip_in / (as_tens * jd), fy)
    else:
        fs_eval = (2.0 / 3.0) * fy

    s_max = check_crack_control_spacing(section, fs=fs_eval, cc=cc)
    s_prov = float(provided_spacing)

    passed = s_prov <= s_max
    messages = []
    if not passed:
        messages.append(
            f"Provided rebar spacing ({s_prov:.1f} in) exceeds ACI 318-19 crack control limit ({s_max:.1f} in) at fs={fs_eval:.1f} ksi."
        )

    return CrackControlResult(
        allowable_spacing=round(s_max, 2),
        provided_spacing=round(s_prov, 2),
        steel_stress_ksi=round(fs_eval, 2),
        clear_cover_in=round(cc, 2),
        passed=passed,
        status="Passed" if passed else "Failed",
        messages=messages,
    )
