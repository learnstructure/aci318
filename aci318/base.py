"""Base model configuration for aci318 schemas."""

from pydantic import BaseModel, ConfigDict


class BaseSchemaModel(BaseModel):
    """Common Pydantic base model with strict validation for aci318."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
    )
