"""
User-facing Wall class.
"""
from typing import Any
from aci318.codes.base import DesignCode
from aci318.loads.load_effects import LoadEffects

class Wall:
    """
    Coordinates wall design calculations.
    """
    def __init__(self, section: Any, code: DesignCode) -> None:
        self.section = section
        self.code = code

    def design(self, loads: LoadEffects) -> Any:
        """Design the wall."""
        return None
