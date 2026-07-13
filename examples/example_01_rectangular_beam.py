"""
Example 01: Rectangular Beam Flexure Design
============================================

This example demonstrates how to design a simply supported rectangular reinforced
concrete beam for flexure and shear using the aci318 library.

Problem:
--------
A 12 in × 24 in rectangular beam spans 20 ft. It is reinforced with 3 #8 bars
(As = 2.37 in²) in a single layer at an effective depth d = 21.5 in.

Material:
  - Concrete: f'c = 4,000 psi (4.0 ksi), normal weight (145 pcf)
  - Steel:    fy  = 60,000 psi (60.0 ksi), Es = 29,000 ksi

Code: ACI 318-19

Design Actions:
  - Mu = 2,500 kip-in (factored bending moment)
  - Vu =   30 kip    (factored shear force)
"""

from aci318.codes.aci318_19 import ACI318_19
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.beam import Beam
from aci318.sections.rectangle import RectangleSection

# ─────────────────────────────────────────────────────────────────────
# 1. Define Materials
# ─────────────────────────────────────────────────────────────────────────────
concrete = Concrete(fc=4.0)          # 4.0 ksi = 4,000 psi
steel    = Steel(fy=60.0)            # 60 ksi = Grade 60

# ─────────────────────────────────────────────────────────────────────────────
# 2. Define Cross Section
# ─────────────────────────────────────────────────────────────────────────────
section = RectangleSection(b=12.0, h=24.0, concrete=concrete)

# 3 #8 bars at d = 21.5 in from extreme compression fiber
# Each #8 bar area = 0.79 in² → 3 bars = 2.37 in²
section.add_rebar_layer(area=2.37, depth=21.5, steel=steel)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Select Design Code and Load Effects
# ─────────────────────────────────────────────────────────────────────────────
code  = ACI318_19()
loads = LoadEffects(Mu=2500.0, Vu=30.0)   # kip-in, kip

# ─────────────────────────────────────────────────────────────────────────────
# 4. Run Design via the Beam Coordinator
# ─────────────────────────────────────────────────────────────────────────────
beam   = Beam(section=section, code=code)
result = beam.design(loads)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Print Results
# ─────────────────────────────────────────────────────────────────────────────
print(result)
# print("=" * 60)
# print("  RECTANGULAR BEAM DESIGN  —  ACI 318-19")
# print("=" * 60)

# print("\n[ Section Properties ]")
# print(f"  Width b          = {section.b:.1f} in")
# print(f"  Height h         = {section.h:.1f} in")
# print(f"  Gross Area  Ag   = {section.gross_area:.1f} in²")
# print(f"  Gross Inertia Ig = {section.gross_inertia:.0f} in⁴")
# print(f"  Tension steel As = {result.flexure.provided_steel:.2f} in²")

# print("\n[ Material Properties ]")
# print(f"  f'c = {concrete.fc:.1f} ksi")
# print(f"  Ec  = {concrete.Ec:.1f} ksi")
# print(f"  fy  = {steel.fy:.1f} ksi")
# print(f"  Es  = {steel.Es:.0f} ksi")

# print("\n[ Flexure Results ]")
# print(f"  Neutral axis c       = {result.flexure.neutral_axis:.3f} in")
# print(f"  Steel strain εt      = {result.flexure.steel_strain:.5f}")
# print(f"  φ·Mn (design)        = {result.flexure.phi_mn:.1f} kip-in")
# print(f"  Mu   (applied)       = {loads.Mu:.1f} kip-in")
# ok_flex = "✓ OK" if result.flexure.phi_mn >= loads.Mu else "✗ NG"
# print(f"  φ·Mn ≥ Mu?           → {ok_flex}  (DCR = {loads.Mu / result.flexure.phi_mn:.3f})")
# if result.flexure.messages:
#     for msg in result.flexure.messages:
#         print(f"  ⚠  {msg}")

# print("\n[ Shear Results ]")
# print(f"  Vc (concrete)        = {result.shear.vn_concrete:.2f} kip")
# print(f"  Vs (stirrups)        = {result.shear.vn_steel:.2f} kip")
# print(f"  φ·Vn (design)        = {result.shear.phi_vn:.2f} kip")
# print(f"  Vu   (applied)       = {loads.Vu:.1f} kip")
# ok_shear = "✓ OK" if result.shear.phi_vn >= loads.Vu else "✗ NG"
# print(f"  φ·Vn ≥ Vu?           → {ok_shear}  (DCR = {loads.Vu / result.shear.phi_vn:.3f})")
# if result.shear.messages:
#     for msg in result.shear.messages:
#         print(f"  ⚠  {msg}")

# print(f"\n[ Overall Status ] → {result.status}")
# print("=" * 60)
