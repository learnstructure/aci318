"""
Footing detailing helpers for isolated, strip, and combined foundations in aci318.
"""

from __future__ import annotations

from typing import List

from .base import BarPlacement, ReinforcementDetail


class IsolatedFootingDetail(ReinforcementDetail):
    """Reinforcement detail for an isolated spread footing member."""

    detail_type: str = "isolated_footing"


def create_isolated_footing_detail(
    member_id: str,
    bottom_bars: List[BarPlacement],
) -> IsolatedFootingDetail:
    """Create an isolated footing detailing object from bottom reinforcement bars."""

    return IsolatedFootingDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        detail_type="isolated_footing",
        bars=bottom_bars,
        notes="Isolated footing detailing generated from ACI design output",
    )


class StripFootingDetail(ReinforcementDetail):
    """Reinforcement detail for a continuous strip / wall footing member."""

    detail_type: str = "strip_footing"


def create_strip_footing_detail(
    member_id: str,
    bars: List[BarPlacement],
) -> StripFootingDetail:
    """Create a strip footing detailing object from reinforcement placements."""

    return StripFootingDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        detail_type="strip_footing",
        bars=bars,
        notes="Continuous strip footing detailing generated from ACI design output",
    )


class CombinedFootingDetail(ReinforcementDetail):
    """Reinforcement detail for a two-column combined rectangular footing member."""

    detail_type: str = "combined_footing"


def create_combined_footing_detail(
    member_id: str,
    bars: List[BarPlacement],
) -> CombinedFootingDetail:
    """Create a combined footing detailing object from reinforcement placements."""

    return CombinedFootingDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        detail_type="combined_footing",
        bars=bars,
        notes="Two-column combined footing detailing generated from ACI design output",
    )


__all__ = [
    "IsolatedFootingDetail",
    "create_isolated_footing_detail",
    "StripFootingDetail",
    "create_strip_footing_detail",
    "CombinedFootingDetail",
    "create_combined_footing_detail",
]
