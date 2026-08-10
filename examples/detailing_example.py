"""Example showing how to create a simple beam detailing object."""

from aci318 import BarPlacement, create_beam_detail

longitudinal_bars = [
    BarPlacement(id="b1", bar_size="#8", count=3, location="bottom", spacing=6.0, cover=1.5),
]
stirrups = [
    BarPlacement(id="s1", bar_size="#3", count=2, location="stirrup", spacing=12.0, cover=1.5),
]

detail = create_beam_detail(member_id="beam-01", longitudinal_bars=longitudinal_bars, stirrups=stirrups)

print(detail.model_dump())
