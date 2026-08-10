"""
Design code provisions interfaces and concrete implementations.
"""

from .aci318_19 import ACI318_19
from .aci318_25 import ACI318_25
from .base import DesignCode

__all__ = [
    "DesignCode",
    "ACI318_19",
    "ACI318_25",
]
