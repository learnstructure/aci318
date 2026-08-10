"""Column detailing helpers for aci318."""

from .base import BarPlacement, ReinforcementDetail


class ColumnDetail(ReinforcementDetail):
    """Reinforcement detail for a column member."""

    detail_type: str = "column"


def create_column_detail(member_id: str, longitudinal_bars: list[BarPlacement], ties: list[BarPlacement]) -> ColumnDetail:
    """Create a column detailing object from longitudinal bars and ties."""

    return ColumnDetail(
        id=f"detail-{member_id}",
        member_id=member_id,
        bars=longitudinal_bars,
        stirrups=ties,
        notes="Column detailing generated from ACI design output",
    )
