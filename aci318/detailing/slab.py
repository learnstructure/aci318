"""Slab detailing helpers for aci318."""

from .base import BarPlacement, ReinforcementDetail


class SlabDetail(ReinforcementDetail):
    """Reinforcement detail for a slab member."""

    detail_type: str = "slab"


def create_slab_detail(member_id: str, main_bars: list[BarPlacement], distribution_bars: list[BarPlacement]) -> SlabDetail:
    """Create a slab detailing object from main and distribution reinforcement."""

    return SlabDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        bars=main_bars + distribution_bars,
        notes="Slab detailing generated from ACI design output",
    )
