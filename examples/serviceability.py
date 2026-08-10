"""
Serviceability example.
"""

from aci318 import Concrete, RectangleSection, Steel
from aci318.serviceability.deflection import calculate_cracking_moment, calculate_effective_inertia
from aci318.serviceability.crack import check_crack_control_spacing

concrete = Concrete(fc=4.0)
steel = Steel(fy=60.0)
section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
section.add_rebar_layer(area=2.37, depth=21.5, steel=steel)

Ma = 1700.0
Icr = 4200.0
cc = 1.5
fs = 36.0

Ig = section.gross_inertia
yt = section.centroid
Mcr = calculate_cracking_moment(section, yt)
Ie = calculate_effective_inertia(section, Ma, Icr)
s_max = check_crack_control_spacing(section, fs, cc)

print(f"Mcr = {Mcr:.1f} kip-in")
print(f"Ie = {Ie:.0f} in⁴")
print(f"s_max = {s_max:.1f} in")
