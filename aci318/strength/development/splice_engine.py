"""
Reinforcement lap splice design engine according to ACI 318-19 §25.5.
"""

from typing import Optional
from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.results.development import DevelopmentResult
from aci318.strength.development.development_length_engine import calculate_development_length


def design_splice(
    bar_size: str,
    steel: Steel,
    concrete: Concrete,
    code: DesignCode,
    splice_class: str = "B",
    is_top_bar: bool = False,
    is_epoxy: bool = False,
) -> DevelopmentResult:
    """
    Compute lap splice length for tension and compression reinforcement (ACI 318-19 §25.5).
    
    Args:
        bar_size: Bar designation, e.g. '#8'.
        steel: Steel material object.
        concrete: Concrete material object.
        code: DesignCode instance.
        splice_class: 'A' or 'B' (Class A = 1.0*ld, Class B = 1.3*ld).
        is_top_bar: True if top horizontal reinforcement (casting depth > 12 in).
        is_epoxy: True if epoxy-coated.
        
    Returns:
        DevelopmentResult dataclass.
    """
    rebar = Rebar(bar_size=bar_size)
    dev_res = calculate_development_length(
        bar_diameter=rebar.diameter,
        steel=steel,
        concrete=concrete,
        code=code,
        is_top_bar=is_top_bar,
        is_epoxy=is_epoxy,
    )

    factor = 1.0 if splice_class.upper() == "A" else 1.3
    tension_splice = max(factor * dev_res.ld_tension, 12.0)

    # Compression lap splice length (ACI 318-19 §25.5.5.1)
    fy_psi = steel.fy * 1000.0
    db = rebar.diameter

    if steel.fy <= 60.0:
        comp_splice = max(0.0005 * fy_psi * db, 12.0)
    else:
        comp_splice = max((0.0009 * fy_psi - 24.0) * db, 12.0)

    # For f'c < 3000 psi, increase compression lap splice by 1/3
    if concrete.fc < 3.0:
        comp_splice *= (4.0 / 3.0)

    return DevelopmentResult(
        ld_tension=dev_res.ld_tension,
        ld_compression=dev_res.ld_compression,
        ldh_hook=dev_res.ldh_hook,
        splice_length=max(tension_splice, comp_splice),
        status="Passed",
        messages=[f"Class {splice_class.upper()} tension lap splice = {tension_splice:.1f} in."],
    )
