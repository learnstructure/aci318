"""
Geometry validators for structural member dimensions and cross-sections.
"""

from aci318.utils.exceptions import GeometryValidationError


def validate_rectangle_geometry(b: float, h: float, cover: float = 1.5) -> None:
    """
    Validate rectangular section dimensions.
    
    Args:
        b: Section width in inches.
        h: Section overall height in inches.
        cover: Clear cover in inches.
        
    Raises:
        GeometryValidationError: If dimensions are non-positive or invalid.
    """
    if b <= 0.0:
        raise GeometryValidationError(f"Section width b must be positive, got {b} inches.")
    if h <= 0.0:
        raise GeometryValidationError(f"Section height h must be positive, got {h} inches.")
    if cover < 0.0:
        raise GeometryValidationError(f"Clear cover must be non-negative, got {cover} inches.")
    if 2.0 * cover >= h or 2.0 * cover >= b:
        raise GeometryValidationError(
            f"Clear cover ({cover} in) is too large for section dimensions b={b} in, h={h} in."
        )


def validate_flange_geometry(b_f: float, h_f: float, b_w: float, h: float) -> None:
    """
    Validate T-beam or L-beam flanged cross-section dimensions.
    
    Args:
        b_f: Effective flange width in inches.
        h_f: Flange thickness in inches.
        b_w: Web width in inches.
        h: Total height in inches.
        
    Raises:
        GeometryValidationError: If dimensions violate structural geometry constraints.
    """
    if b_w <= 0.0:
        raise GeometryValidationError(f"Web width b_w must be positive, got {b_w} in.")
    if b_f < b_w:
        raise GeometryValidationError(f"Flange width b_f ({b_f} in) cannot be smaller than web width b_w ({b_w} in).")
    if h_f <= 0.0 or h_f >= h:
        raise GeometryValidationError(f"Flange thickness h_f ({h_f} in) must be positive and less than total height h ({h} in).")
