"""Beam design result to detailing example."""

from aci318 import (
    ACI318_19,
    Beam,
    Concrete,
    LoadEffects,
    RectangleSection,
    create_beam_detail_from_design_result,
)

concrete = Concrete(fc=4.0)
code = ACI318_19()
loads = LoadEffects(Mu=2500.0, Vu=30.0)

section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
beam = Beam(
    section=section,
    code=code,
    stirrup_bar_size="#3",
    stirrup_legs=2,
    fy_shear=60.0,
)

design_result = beam.design(loads)

detail = create_beam_detail_from_design_result(
    design_result=design_result,
    member_id="beam-01",
)

print("Design status:", design_result.status)
print("Suggested bars:", design_result.suggested_bars)
print("Detailing object:")
print(detail.model_dump())
