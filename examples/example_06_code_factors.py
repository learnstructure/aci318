"""
Example 06: ACI 318 Code Provisions — Phi, Beta1, and Lambda Factors
=====================================================================

This example explores how the code abstraction layer works by querying
ACI 318-19 design code factors directly.

It demonstrates:
  1. How phi (φ) varies with tensile strain (flexure-controlled vs
     compression-controlled vs transition zone).
  2. How beta_1 (β₁) varies with concrete compressive strength f'c.
  3. How the lightweight concrete modification factor lambda (λ) applies.

Code: ACI 318-19
"""

from aci318.codes.aci318_19 import ACI318_19
from aci318.materials.concrete import Concrete

code = ACI318_19()

# ─────────────────────────────────────────────────────────────────────────────
# 1. Phi Factor for Flexure — Transition Zone Behavior
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("  ACI 318-19 DESIGN CODE FACTORS")
print("=" * 60)

print("\n[ φ Flexure vs. Net Tensile Strain εt  (ACI Table 21.2.2) ]")
print(f"  {'εt':>10}  {'φ (tied)':>10}  {'Classification':>20}")
print("-" * 50)

strains = [0.000, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.010]
for eps in strains:
    phi = code.get_phi_flexure(strain_t=eps)
    if eps < 0.002:
        cls = "Compression-controlled"
    elif eps > 0.005:
        cls = "Tension-controlled"
    else:
        cls = "Transition zone"
    print(f"  {eps:>10.4f}  {phi:>10.3f}  {cls:>20}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Beta_1 Factor — Varies with f'c
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ β₁ Factor vs. f'c  (ACI Table 22.2.2.4.3) ]")
print(f"  {'f\'c (ksi)':>10}  {'f\'c (psi)':>10}  {'β₁':>8}")
print("-" * 35)

fc_list = [2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]
for fc in fc_list:
    beta1 = code.get_beta_1(fc)
    print(f"  {fc:>10.1f}  {fc*1000:>10,.0f}  {beta1:>8.3f}")

# ─────────────────────────────────────────────────────────────────────────────
# 3. Phi Factors for Other Failure Modes
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ φ Factors for Other Failure Modes ]")
print(f"  Shear   φ                    = {code.get_phi_shear():.2f}")
print(f"  Axial compression (tied)     = {code.get_phi_axial(compression=True, spiral=False):.2f}")
print(f"  Axial compression (spiral)   = {code.get_phi_axial(compression=True, spiral=True):.2f}")
print(f"  Axial tension                = {code.get_phi_axial(compression=False):.2f}")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Lambda Factor — Lightweight Concrete
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ λ Lightweight Concrete Modification Factor  (ACI §19.2.4) ]")

nw_concrete = Concrete(fc=4.0, concrete_type="normalweight", density=145.0)
sl_concrete = Concrete(fc=4.0, concrete_type="sand-lightweight", density=120.0)
al_concrete = Concrete(fc=4.0, concrete_type="all-lightweight", density=105.0)

for label, conc in [("Normal weight", nw_concrete),
                     ("Sand-lightweight", sl_concrete),
                     ("All-lightweight", al_concrete)]:
    lam = code.get_lambda_(conc)
    print(f"  {label:<20}: λ = {lam:.2f}  (density = {conc.density:.0f} pcf)")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Minimum Steel Ratio
# ─────────────────────────────────────────────────────────────────────────────
print("\n[ Minimum Flexural Reinforcement Ratio  (ACI §9.6.1.2) ]")
fc_vals = [3.0, 4.0, 5.0, 6.0]
fy_vals = [40.0, 60.0, 80.0]

print(f"  {'f\'c':>6}  {'fy = 40 ksi':>12}  {'fy = 60 ksi':>12}  {'fy = 80 ksi':>12}")
print("-" * 50)
for fc in fc_vals:
    row = f"  {fc:>6.1f}"
    for fy in fy_vals:
        rho_min = code.get_minimum_steel_ratio(fc=fc, fy=fy)
        row += f"  {rho_min:>12.5f}"
    print(row)

print("=" * 60)
