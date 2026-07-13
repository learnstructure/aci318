"""
Crack control verification (e.g., maximum rebar spacing for crack control ACI 318 Section 24.3.2).
"""
from aci318.sections.rectangle import RectangleSection

def check_crack_control_spacing(
    section: RectangleSection,
    fs: float,                  # Calculated steel stress at service load (ksi)
    cc: float                   # Clear cover to tension reinforcement (in)
) -> float:
    """
    Returns the maximum allowable spacing of tension reinforcement for crack control (in).
    ACI 318-19 Section 24.3.2: s = min(15 * (40000/fs) - 2.5*cc, 12 * (40000/fs))
    where fs and cc are in psi/inches.
    """
    fs_psi = fs * 1000.0
    val1 = 15.0 * (40000.0 / fs_psi) - 2.5 * cc
    val2 = 12.0 * (40000.0 / fs_psi)
    return min(val1, val2)
