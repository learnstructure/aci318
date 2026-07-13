"""
Example 02: Column Axial Capacity
==================================

This example demonstrates how to check a short tied rectangular column for
pure axial compression using the aci318 library.

Problem:
--------
A 14 in × 14 in tied column is reinforced with 8 #8 bars (Ast = 6.32 in²).

Material:
  - Concrete: f'c = 5,000 psi (5.0 ksi), normal weight
  - Steel:    fy  = 60,000 psi (60 ksi)

Code: ACI 318-19

Design Action:
  - Pu = 650 kip (factored axial load)
"""

from aci318.codes.aci318_19 import ACI318_19
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.strength.axial.column_engine import calculate_axial_capacity

# ─────────────────────────────────────────────────────────────────────────────
# 1. Define Materials
# ─────────────────────────────────────────────────────────────────────────────
concrete = Concrete(fc=5.0)      # 5.0 ksi
steel    = Steel(fy=60.0)        # Grade 60

# ─────────────────────────────────────────────────────────────────────────────
# 2. Define Cross Section
# ─────────────────────────────────────────────────────────────────────────────
section = RectangleSection(b=14.0, h=14.0, concrete=concrete)

# 8 #8 bars symmetrically placed
# 8 × 0.79 in² = 6.32 in²
# Place as 4 corners at d = 2.5 in and d = 11.5 in (each face)
section.add_rebar_layer(area=3.16, depth=2.5,  steel=steel)  # top 4 bars
section.add_rebar_layer(area=3.16, depth=11.5, steel=steel)  # bottom 4 bars

# ─────────────────────────────────────────────────────────────────────────────
# 3. Select Design Code
# ─────────────────────────────────────────────────────────────────────────────
code = ACI318_19()

# ─────────────────────────────────────────────────────────────────────────────
# 4. Calculate Axial Capacity (tied column, spiral=False)
# ─────────────────────────────────────────────────────────────────────────────
Pu     = 650.0   # kip (factored axial load)
result = calculate_axial_capacity(section, code, spiral=False)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Print Results
# ─────────────────────────────────────────────────────────────────────────────
Ag  = section.gross_area
Ast = sum(lyr.area for lyr in section.layers)
rho = Ast / Ag

print("=" * 60)
print("  RECTANGULAR TIED COLUMN  —  ACI 318-19")
print("=" * 60)

print("\n[ Section Properties ]")
print(f"  Size  b × h     = {section.b:.0f} in × {section.h:.0f} in")
print(f"  Gross Area  Ag  = {Ag:.1f} in²")
print(f"  Steel Area  Ast = {Ast:.2f} in²")
print(f"  Steel Ratio ρg  = {rho:.4f}  ({rho*100:.2f}%)")

print("\n[ Material Properties ]")
print(f"  f'c = {concrete.fc:.1f} ksi   Ec = {concrete.Ec:.0f} ksi")
print(f"  fy  = {steel.fy:.1f} ksi   Es = {steel.Es:.0f} ksi")

print("\n[ ACI 318-19 Phi Factors ]")
phi = code.get_phi_axial(compression=True, spiral=False)
print(f"  φ (tied column)  = {phi:.2f}")

print("\n[ Axial Capacity Results ]")
print(f"  Pn0   (zero-eccentricity)  = {result.pn_nominal:.1f} kip")
print(f"  Pn_max (0.80·Pn0, tied)    = {result.pn_max:.1f} kip")
print(f"  φ·Pn_max (design strength) = {result.phi_pn_max:.1f} kip")
print(f"  Pu    (applied load)       = {Pu:.1f} kip")

ok = "✓ OK" if result.phi_pn_max >= Pu else "✗ NG"
dcr = Pu / result.phi_pn_max
print(f"  φ·Pn_max ≥ Pu?             → {ok}  (DCR = {dcr:.3f})")

if result.messages:
    print("\n[ Warnings ]")
    for msg in result.messages:
        print(f"  ⚠  {msg}")

print(f"\n[ Overall Status ] → {result.status}")
print("=" * 60)
