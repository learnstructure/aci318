"""Beam detailing helpers for aci318."""

from typing import List, Optional

from aci318.results.beam import BeamDesignResult

from .base import BarPlacement, ReinforcementDetail


class BeamDetail(ReinforcementDetail):
    """Reinforcement detail for a beam member."""

    detail_type: str = "beam"


def create_beam_detail(member_id: str, longitudinal_bars: List[BarPlacement], stirrups: List[BarPlacement]) -> BeamDetail:
    """Create a beam detailing object from longitudinal bars and stirrups."""

    return BeamDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        bars=longitudinal_bars,
        stirrups=stirrups,
        notes="Beam detailing generated from ACI design output",
    )


def create_beam_detail_from_design_result(
    design_result: BeamDesignResult,
    member_id: str = "beam-01",
    cover: float = 1.5,
    location: str = "bottom",
) -> BeamDetail:
    """Create a beam detailing object directly from a beam design result."""

    longitudinal_bars: List[BarPlacement] = []
    if design_result.suggested_bars and design_result.suggested_bars.lower() != "none":
        count_text, bar_size = design_result.suggested_bars.split()
        longitudinal_bars = [
            BarPlacement(
                id=f"{member_id}-longitudinal-1",
                bar_size=bar_size,
                count=int(count_text),
                location=location,
                spacing=design_result.required_shear_spacing,
                cover=cover,
            )
        ]

    stirrups = [
        BarPlacement(
            id=f"{member_id}-stirrup-1",
            bar_size=design_result.stirrup_bar_size,
            count=design_result.stirrup_legs,
            location="stirrup",
            spacing=design_result.required_shear_spacing,
            cover=cover,
        )
    ]

    return create_beam_detail(
        member_id=member_id,
        longitudinal_bars=longitudinal_bars,
        stirrups=stirrups,
    )
