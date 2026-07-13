"""
Example 04: Serviceability Checks — Cracking and Effective Inertia
===================================================================

This example demonstrates serviceability-level checks using the aci318
library. It computes:
  1. The cracking moment Mcr (ACI 318-19 Section 19.2.3)
  2. The effective moment of inertia Ie (ACI 318-19 Section 24.2.3.5)
  3. The maximum allowable crack-control bar spacing (ACI 318-19 Section 24.3.2)

Problem:
--------
Same 12 in × 24 in rectangular beam with 3 #8 bars at d = 21.5 in.
Under service loads: Ma = 1,700 kip-in (after dead-load deflection).
Assumed cracked moment of inertia: Icr = 4,200 in⁴
Clear cover to tension reinforcement: cc = 1.5 in
Service steel stress: fs = 0.6 × fy = 36 ksi

Material: f'c = 4.0 ksi, fy = 60.0 ksi
"""

from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.serviceability.deflection import calculate_cracking_moment, calculate_effective_inertia
from aci318.serviceability.crack import check_crack_control_spacing

# ─────────────────────────────────────────────────────────────────────────────
# 1. Define Materials and Section
# ─────────────────────────────────────────────────────────────────────────────
concrete = Concrete(fc=4.0)
steel    = Steel(fy=60.0)
section  = RectangleSection(b=12.0, h=24.0, concrete=concrete)
section.add_rebar_layer(area=2.37, depth=21.5, steel=steel)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Service Conditions
# ─────────────────────────────────────────────────────────────────────────────
Ma  = 1700.0   # Service bending moment (kip-in)
Icr = 4200.0   # Cracked section moment of inertia (in⁴) — user-computed from transformed section
cc  = 1.5      # Clear cover to tension bars (in)
fs  = 36.0     # Service steel stress ≈ 0.6 × fy (ksi)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Compute Section Properties
# ─────────────────────────────────────────────────────────────────────────────
Ig  = section.gross_inertia
yt  = section.centroid
Mcr = calculate_cracking_moment(section, yt)
Ie  = calculate_effective_inertia(section, Ma, Icr)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Crack Control Bar Spacing
# ─────────────────────────────────────────────────────────────────────────────
s_max = check_crack_control_spacing(section, fs, cc)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Approximate mid-span deflection (simply supported, uniform load case)
#    Δ = 5 × w × L⁴ / (384 × Ec × Ie)
#    This is shown symbolically — user must supply span L and uniform load w.
# ─────────────────────────────────────────────────────────────────────────────
L_in = 20 * 12.0  # 20 ft span in inches
Ec   = concrete.Ec

# Example: if the uniform load w corresponds to Ma = wL²/8 → w = 8*Ma/L²
w_kinch = 8.0 * Ma / (L_in ** 2)   # kip/in equivalent
delta   = (5.0 * w_kinch * L_in**4) / (384.0 * Ec * Ie)

# ─────────────────────────────────────────────────────────────────────────────
# 6. Print Results
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 60)
print("  SERVICEABILITY CHECKS  —  ACI 318-19")
print("=" * 60)

print("\n[ Section Properties ]")
print(f"  Gross Inertia  Ig  = {Ig:,.0f} in⁴")
print(f"  Cracked Inertia Icr = {Icr:,.0f} in⁴   (user-supplied)")
print(f"  Centroid  yt       = {yt:.1f} in")
print(f"  Ec                 = {Ec:.0f} ksi")

print("\n[ Cracking Moment  (ACI 318-19, §19.2.3) ]")
print(f"  fr  = 7.5 × λ × √f'c = 7.5 × √4000 = {7.5*(concrete.fc*1000)**0.5:.1f} psi")
print(f"  Mcr = fr × Ig / yt   = {Mcr:.1f} kip-in")
if Ma < Mcr:
    print(f"  Ma = {Ma:.0f} kip-in < Mcr → Section is UNCRACKED → Ie = Ig")
else:
    print(f"  Ma = {Ma:.0f} kip-in > Mcr → Section is CRACKED → use Ie < Ig")

print("\n[ Effective Moment of Inertia  (ACI 318-19, §24.2.3.5) ]")
print(f"  Ma  = {Ma:.0f} kip-in")
print(f"  Mcr = {Mcr:.1f} kip-in")
print(f"  Ie  = {Ie:,.0f} in⁴   (Icr ≤ Ie ≤ Ig)")

print("\n[ Estimated Immediate Deflection  (simply-supported, uniform load) ]")
print(f"  Span L      = {L_in/12:.0f} ft  ({L_in:.0f} in)")
print(f"  Applied Ma  = {Ma:.0f} kip-in  (→ w ≈ {w_kinch*1000:.2f} plf equivalent)")
print(f"  Δ_immediate = {delta:.3f} in  =  L/{L_in/delta:.0f}")

L_limit_240 = L_in / 240
L_limit_360 = L_in / 360
print(f"  ACI L/240 limit = {L_limit_240:.3f} in  {'✓ OK' if delta <= L_limit_240 else '✗ Exceeds limit'}")
print(f"  ACI L/360 limit = {L_limit_360:.3f} in  {'✓ OK' if delta <= L_limit_360 else '✗ Exceeds limit'}")

print("\n[ Crack Control Bar Spacing  (ACI 318-19, §24.3.2) ]")
print(f"  fs  = {fs:.0f} ksi  (= 0.60 × fy)")
print(f"  cc  = {cc:.1f} in  (clear cover)")
print(f"  s_max = {s_max:.1f} in")
print("  (Actual bar spacing should be ≤ s_max)")
print("=" * 60)
