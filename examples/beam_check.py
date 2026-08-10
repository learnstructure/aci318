"""
Beam check example.
"""

from aci318 import ACI318_19, Beam, BeamTextReport, Concrete, LoadEffects, RectangleSection, Steel

concrete = Concrete(fc=4.0)
steel = Steel(fy=60.0)
section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
section.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)

code = ACI318_19()
loads = LoadEffects(Mu=2500.0, Vu=30.0)

beam = Beam(section=section, code=code)
result = beam.check(loads)

report = BeamTextReport(section, loads, result)
report.print_to_console()
