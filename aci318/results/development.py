from dataclasses import dataclass, field
from typing import Any, List

@dataclass
class DevelopmentResult:
    """
    Result object storing outputs from development length and anchorage design engines.
    """
    ld_tension: float           # Required tension development length (in)
    ld_compression: float       # Required compression development length (in)
    ldh_hook: float             # Required hook development length (in)
    splice_length: float        # Required lap splice length (in)
    status: str
    messages: List[str] = field(default_factory=list)
    defaults_applied: List[Any] = field(default_factory=list)
