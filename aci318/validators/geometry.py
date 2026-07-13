"""
Geometry validators.
"""

def validate_dimensions(width: float, height: float) -> None:
    """Validate cross-sectional width and height."""
    if width <= 0:
        raise ValueError(f"Width must be positive, got {width}")
    if height <= 0:
        raise ValueError(f"Height must be positive, got {height}")
