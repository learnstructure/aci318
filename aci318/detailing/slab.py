"""Slab detailing helpers for aci318."""

from typing import List, Optional
from .base import BarPlacement, ReinforcementDetail


class SlabDetail(ReinforcementDetail):
    """Reinforcement detail for a slab member."""

    detail_type: str = "slab"


def create_slab_detail(
    member_id: str,
    main_bars: Optional[List[BarPlacement]] = None,
    distribution_bars: Optional[List[BarPlacement]] = None,
    bars: Optional[List[BarPlacement]] = None,
) -> SlabDetail:
    """Create a slab detailing object from main and distribution reinforcement."""
    all_bars = bars or []
    if main_bars:
        all_bars.extend(main_bars)
    if distribution_bars:
        all_bars.extend(distribution_bars)

    return SlabDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        bars=all_bars,
        notes="Slab detailing generated from ACI design output",
    )
