"""Footing detailing helpers for aci318."""

from .base import BarPlacement, ReinforcementDetail


class FootingDetail(ReinforcementDetail):
    """Reinforcement detail for a footing member."""

    detail_type: str = "footing"


def create_footing_detail(member_id: str, bottom_bars: list[BarPlacement]) -> FootingDetail:
    """Create a footing detailing object from bottom reinforcement bars."""

    return FootingDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        bars=bottom_bars,
        notes="Footing detailing generated from ACI design output",
    )
