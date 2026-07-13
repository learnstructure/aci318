"""
Example 03: Development Length and Lap Splice
==============================================

This example demonstrates how to compute required tension development lengths,
compression development lengths, standard hook development lengths, and Class B
lap splice lengths for common ASTM bar sizes.

Material:
  - Concrete: f'c = 4,000 psi, normal weight
  - Steel:    fy  = 60,000 psi (Grade 60)

Bars: #4, #6, #8, #10 (bottom (non-top) bars in normalweight concrete)

Code: ACI 318-19
"""

from aci318.codes.aci318_19 import ACI318_19
from aci318.database.bars import BAR_DATABASE
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.strength.development.development_length_engine import calculate_development_length

# ─────────────────────────────────────────────────────────────────────────────
# 1. Define Materials and Code
# ─────────────────────────────────────────────────────────────────────────────
concrete = Concrete(fc=4.0)
steel    = Steel(fy=60.0)
code     = ACI318_19()

bar_sizes = ["#4", "#6", "#8", "#10"]

# ─────────────────────────────────────────────────────────────────────────────
# 2. Loop through bar sizes and compute development lengths
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 80)
print("  DEVELOPMENT LENGTH TABLE  —  ACI 318-19")
print(f"  f'c = {concrete.fc:.1f} ksi   fy = {steel.fy:.0f} ksi   Normal Weight Concrete")
print("=" * 80)
print(f"  {'Bar':>4}  {'db (in)':>8}  {'Ab (in²)':>9}  "
      f"{'ld_t (in)':>10}  {'ld_c (in)':>10}  {'ldh (in)':>9}  {'ls_B (in)':>10}")
print("-" * 80)

for bar in bar_sizes:
    db = BAR_DATABASE[bar]["diameter"]
    ab = BAR_DATABASE[bar]["area"]

    result = calculate_development_length(
        bar_diameter=db,
        steel=steel,
        concrete=concrete,
        code=code,
        is_top_bar=False,    # bottom bar (most common case)
        is_epoxy=False,
        is_lightweight=False
    )

    print(f"  {bar:>4}  {db:>8.3f}  {ab:>9.2f}  "
          f"{result.ld_tension:>10.1f}  {result.ld_compression:>10.1f}  "
          f"{result.ldh_hook:>9.1f}  {result.splice_length:>10.1f}")

print("-" * 80)
print("  ld_t = tension development length (in)")
print("  ld_c = compression development length (in)")
print("  ldh  = standard hook development length (in)")
print("  ls_B = Class B lap splice length = 1.3 × ld_t (in)")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Compare top-bar vs bottom-bar for a #8 bar
# ─────────────────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("  TOP BAR vs BOTTOM BAR COMPARISON  (#8 bar)")
print("=" * 60)

db_8 = BAR_DATABASE["#8"]["diameter"]

r_bottom = calculate_development_length(db_8, steel, concrete, code, is_top_bar=False)
r_top    = calculate_development_length(db_8, steel, concrete, code, is_top_bar=True)

print(f"\n  #8 Bottom bar (ψt = 1.0):")
print(f"    ld_tension  = {r_bottom.ld_tension:.1f} in")
print(f"    splice (B)  = {r_bottom.splice_length:.1f} in")

print(f"\n  #8 Top bar (ψt = 1.3, more than 12 in of concrete below):")
print(f"    ld_tension  = {r_top.ld_tension:.1f} in")
print(f"    splice (B)  = {r_top.splice_length:.1f} in")

factor = r_top.ld_tension / r_bottom.ld_tension
print(f"\n  Top-bar increase factor = {factor:.2f}× (should be 1.30)")
print("=" * 60)
