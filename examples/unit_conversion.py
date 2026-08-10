"""
Unit conversion example.
"""

from aci318 import ACI318_19, Beam, Concrete, LoadEffects, RectangleSection, Steel
from aci318.utils.units import convert_length, convert_stress, convert_force, convert_moment

b_mm = 300.0
h_mm = 600.0
d_mm = 540.0
As_mm2 = 1500.0
fc_MPa = 28.0
fy_MPa = 420.0
Mu_kNm = 280.0
Vu_kN = 130.0

b_in = convert_length(b_mm, "mm", "in")
h_in = convert_length(h_mm, "mm", "in")
d_in = convert_length(d_mm, "mm", "in")
As_in2 = As_mm2 * (convert_length(1.0, "mm", "in") ** 2)
fc_ksi = convert_stress(fc_MPa, "mpa", "ksi")
fy_ksi = convert_stress(fy_MPa, "mpa", "ksi")
Mu_kipin = convert_moment(Mu_kNm, "kn-m", "kip-in")
Vu_kip = convert_force(Vu_kN, "kn", "kip")

concrete = Concrete(fc=fc_ksi)
steel = Steel(fy=fy_ksi)
section = RectangleSection(b=b_in, h=h_in, concrete=concrete)
section.add_rebar_layer(area=As_in2, depth=d_in, steel=steel)

code = ACI318_19()
loads = LoadEffects(Mu=Mu_kipin, Vu=Vu_kip)
beam = Beam(section=section, code=code)
result = beam.design(loads)

print(f"phi·Mn = {result.flexure.phi_mn:.1f} kip-in")
print(f"phi·Vn = {result.shear.phi_vn:.1f} kip")
