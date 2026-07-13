"""
Example 05: Unit Conversion — SI to US Customary
=================================================

The aci318 library works exclusively in US customary units internally
(kip, inch, ksi, kip-in). This example demonstrates how to:
  1. Convert input data from SI units into the library's internal units.
  2. Run a design.
  3. Convert the results back to SI for reporting.

Problem Statement (in SI):
--------------------------
A rectangular beam 300 mm × 600 mm is reinforced with 3 bars of 25M
(db = 25 mm, Ab ≈ 500 mm²/bar → As = 1500 mm² total).
The effective depth d = 540 mm.

Factored loads:
  Mu = 280 kN·m
  Vu =  130 kN

Material:
  f'c = 28 MPa  (≈ 4.0 ksi)
  fy  = 420 MPa (≈ Grade 60)
"""

from aci318.codes.aci318_19 import ACI318_19
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.beam import Beam
from aci318.sections.rectangle import RectangleSection
from aci318.utils.units import (
    convert_length,
    convert_stress,
    convert_force,
    convert_moment,
)

# ─────────────────────────────────────────────────────────────────────────────
# 1. Input in SI Units
# ─────────────────────────────────────────────────────────────────────────────
b_mm    = 300.0    # mm
h_mm    = 600.0    # mm
d_mm    = 540.0    # mm  (effective depth)
As_mm2  = 1500.0   # mm²  (3 × 500 mm²)

fc_MPa  = 28.0     # MPa
fy_MPa  = 420.0    # MPa

Mu_kNm  = 280.0    # kN·m
Vu_kN   = 130.0    # kN

print("=" * 60)
print("  SI → US CUSTOMARY UNIT CONVERSION")
print("=" * 60)
print("\n[ Input (SI) ]")
print(f"  b   = {b_mm:.0f} mm")
print(f"  h   = {h_mm:.0f} mm")
print(f"  d   = {d_mm:.0f} mm")
print(f"  As  = {As_mm2:.0f} mm²")
print(f"  f'c = {fc_MPa:.0f} MPa")
print(f"  fy  = {fy_MPa:.0f} MPa")
print(f"  Mu  = {Mu_kNm:.0f} kN·m")
print(f"  Vu  = {Vu_kN:.0f} kN")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Convert to Internal Units (kip, in, ksi, kip-in)
# ─────────────────────────────────────────────────────────────────────────────
b_in    = convert_length(b_mm,   "mm", "in")
h_in    = convert_length(h_mm,   "mm", "in")
d_in    = convert_length(d_mm,   "mm", "in")
As_in2  = As_mm2 * (convert_length(1.0, "mm", "in") ** 2)

fc_ksi  = convert_stress(fc_MPa, "mpa", "ksi")
fy_ksi  = convert_stress(fy_MPa, "mpa", "ksi")

Mu_kipin = convert_moment(Mu_kNm, "kn-m", "kip-in")
Vu_kip   = convert_force(Vu_kN,  "kn",   "kip")

print("\n[ Converted Inputs (US Customary) ]")
print(f"  b   = {b_in:.3f} in")
print(f"  h   = {h_in:.3f} in")
print(f"  d   = {d_in:.3f} in")
print(f"  As  = {As_in2:.4f} in²")
print(f"  f'c = {fc_ksi:.3f} ksi")
print(f"  fy  = {fy_ksi:.3f} ksi")
print(f"  Mu  = {Mu_kipin:.1f} kip-in")
print(f"  Vu  = {Vu_kip:.2f} kip")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Build Library Objects and Run Design
# ─────────────────────────────────────────────────────────────────────────────
concrete = Concrete(fc=fc_ksi)
steel    = Steel(fy=fy_ksi)
section  = RectangleSection(b=b_in, h=h_in, concrete=concrete)
section.add_rebar_layer(area=As_in2, depth=d_in, steel=steel)

code   = ACI318_19()
loads  = LoadEffects(Mu=Mu_kipin, Vu=Vu_kip)
beam   = Beam(section=section, code=code)
result = beam.design(loads)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Convert Results Back to SI
# ─────────────────────────────────────────────────────────────────────────────
phi_Mn_kNm = convert_moment(result.flexure.phi_mn, "kip-in", "kn-m")
phi_Vn_kN  = convert_force(result.shear.phi_vn,   "kip",    "kn")
c_mm       = convert_length(result.flexure.neutral_axis, "in", "mm")

print("\n[ Design Results (SI output) ]")
print(f"\n  Flexure:")
print(f"    Neutral axis c  = {c_mm:.1f} mm")
print(f"    Steel strain εt = {result.flexure.steel_strain:.5f}")
print(f"    φ·Mn            = {phi_Mn_kNm:.1f} kN·m")
print(f"    Mu applied      = {Mu_kNm:.1f} kN·m")
ok_f = "✓ OK" if phi_Mn_kNm >= Mu_kNm else "✗ NG"
print(f"    φ·Mn ≥ Mu?      → {ok_f}")

print(f"\n  Shear:")
print(f"    Vc concrete     = {convert_force(result.shear.vn_concrete, 'kip', 'kn'):.1f} kN")
print(f"    φ·Vn            = {phi_Vn_kN:.1f} kN")
print(f"    Vu applied      = {Vu_kN:.1f} kN")
ok_v = "✓ OK" if phi_Vn_kN >= Vu_kN else "✗ NG"
print(f"    φ·Vn ≥ Vu?      → {ok_v}")

print(f"\n[ Overall Status ] → {result.status}")
print("=" * 60)
