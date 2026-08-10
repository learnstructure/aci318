"""
Base model configuration for aci318 schemas with zero external dependency fallback.
"""

from dataclasses import dataclass, field

try:
    from pydantic import BaseModel, ConfigDict

    class BaseSchemaModel(BaseModel):
        """Common Pydantic base model with strict validation for aci318."""

        model_config = ConfigDict(
            extra="forbid",
            populate_by_name=True,
            validate_assignment=True,
        )
except ImportError:
    @dataclass
    class BaseSchemaModel:
        """Fallback dataclass base model when pydantic is not installed."""
        pass
