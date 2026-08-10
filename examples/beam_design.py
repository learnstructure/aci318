"""
Beam design example.
"""

from aci318 import ACI318_19, Beam, BeamTextReport, Concrete, LoadEffects, RectangleSection

concrete = Concrete(fc=4.0)
code = ACI318_19()
loads = LoadEffects(Mu=2500.0, Vu=30.0)

clean_section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
beam = Beam(
    section=clean_section,
    code=code,
    stirrup_bar_size="#3",
    stirrup_legs=2,
    fy_shear=60.0,
)

design_result = beam.design(loads)

report = BeamTextReport(clean_section, loads, design_result)
report.print_to_console()
