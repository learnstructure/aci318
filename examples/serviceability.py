"""
Serviceability & Deflection Analysis Example.

Demonstrates:
1. Computing cracking moment (Mcr) for concrete cross-sections.
2. Calculating effective moment of inertia (Ie) under service load levels.
3. Checking maximum allowable rebar spacing for flexural crack control per ACI 318-19 §24.3.2.
"""

from aci318 import Concrete, RectangleSection, Steel
from aci318.serviceability.crack import check_crack_control_spacing
from aci318.serviceability.deflection import (
    calculate_cracking_moment,
    calculate_effective_inertia,
)

def run_serviceability_example():
    concrete = Concrete(fc=4.0)  # f'c = 4 ksi
    steel = Steel(fy=60.0)      # fy = 60 ksi

    # Rectangular Beam 12" x 24" with 3 #8 bars (As = 2.37 in², d = 21.5")
    section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
    section.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)

    # Gross moment of inertia Ig and neutral axis distance yt
    Ig = section.gross_inertia
    yt = section.centroid

    # 1. Cracking Moment Mcr
    Mcr = calculate_cracking_moment(section, yt)

    # 2. Effective Moment of Inertia Ie under service moment Ma = 1200 kip-in
    Ma = 1200.0  # Service unfactored bending moment (kip-in)
    Icr = 4200.0 # Cracked transformed moment of inertia (in⁴)
    Ie = calculate_effective_inertia(section, Ma, Icr)

    # 3. Maximum Crack Control Bar Spacing s_max (ACI 318-19 §24.3.2)
    # Service stress fs = 2/3 * fy = 40 ksi, clear cover cc = 2.0 in
    fs = 40.0
    cc = 2.0
    s_max = check_crack_control_spacing(section, fs, cc)

    print("=" * 60)
    print(" SERVICEABILITY & CRACK CONTROL ANALYSIS")
    print("=" * 60)
    print(f"Gross Inertia Ig:           {Ig:.0f} in⁴")
    print(f"Cracked Inertia Icr:        {Icr:.0f} in⁴")
    print(f"Cracking Moment Mcr:        {Mcr:.1f} kip-in ({Mcr / 12:.1f} kip-ft)")
    print(f"Service Unfactored Moment Ma:{Ma:.1f} kip-in")
    print(f"Effective Inertia Ie:       {Ie:.0f} in⁴")
    print("-" * 60)
    print(f"Service Steel Stress fs:    {fs:.1f} ksi")
    print(f"Clear Cover cc:             {cc:.1f} in")
    print(f"Max Crack Control Spacing:  {s_max:.1f} in o.c.")
    print("=" * 60)

if __name__ == "__main__":
    run_serviceability_example()
