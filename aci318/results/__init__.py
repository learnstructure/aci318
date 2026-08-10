"""Dataclasses representing intermediate and final calculation results."""

from .axial import AxialResult
from .beam import BeamCheckResult, BeamDesignResult
from .column import ColumnDesignResult
from .development import DevelopmentResult
from .flexure import FlexureResult
from .interaction import InteractionResult, PMInteractionResult
from .shear import ShearResult
from .slab import SlabDesignResult
from .torsion import TorsionResult
from .wall import WallDesignResult

__all__ = [
    "AxialResult",
    "BeamCheckResult",
    "BeamDesignResult",
    "ColumnDesignResult",
    "DevelopmentResult",
    "FlexureResult",
    "InteractionResult",
    "PMInteractionResult",
    "ShearResult",
    "SlabDesignResult",
    "TorsionResult",
    "WallDesignResult",
]
