from abc import ABC, abstractmethod
from aci318.codes.base import DesignCode
from aci318.loads.load_effects import LoadEffects
from aci318.sections.rectangle import RectangleSection


class StrengthChecker(ABC):
    """Base class for modular strength checkers used by members."""

    def __init__(self, section: RectangleSection, code: DesignCode) -> None:
        self.section = section
        self.code = code

    @abstractmethod
    def check(self, loads: LoadEffects):
        """Return a strength result object for the supplied load effects."""
        raise NotImplementedError
