"""
Serviceability & Deflection Analysis Example.

Demonstrates:
1. Computing cracking moment (Mcr) for concrete cross-sections.
2. Calculating effective moment of inertia (Ie) under service load levels.
3. Checking maximum allowable rebar spacing for flexural crack control per ACI 318-19 §24.3.2.
"""

from aci318 import Concrete, RectangleSection, Steel
from aci318.serviceability.crack import check_crack_control_spacing, verify_crack_control
from aci318.serviceability.deflection import (
    calculate_beam_deflection,
    calculate_cracked_inertia,
    calculate_cracking_moment,
    calculate_effective_inertia,
    calculate_long_term_factor,
)

def run_serviceability_example():
    concrete = Concrete(fc=4.0)  # f'c = 4 ksi
    steel = Steel(fy=60.0)      # fy = 60 ksi

    # Rectangular Beam 12" x 24" with 3 #8 bars (As = 2.37 in^2, d = 21.5")
    section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
    section.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)

    # Gross moment of inertia Ig and neutral axis distance yt
    Ig = section.gross_inertia
    yt = section.centroid

    # 1. Cracking Moment Mcr
    Mcr = calculate_cracking_moment(section, yt)

    # 2. Cracked Transformed Inertia Icr & Effective Inertia Ie
    Icr = calculate_cracked_inertia(section)
    Ma = 1200.0  # Service unfactored bending moment (kip-in)
    Ie = calculate_effective_inertia(section, Ma, Icr)

    # 3. Crack Control Verification (ACI 318-19 §24.3.2)
    crack_res = verify_crack_control(
        section=section,
        provided_spacing=4.0,
        ms_service_kip_in=Ma,
        cc=2.0,
    )

    # 4. Long-Term and Live Load Deflection Evaluation (ACI 318-19 §24.2)
    # 24-ft simple span with w_dead = 1.0 kip/ft (0.0833 kip/in) and w_live = 0.6 kip/ft (0.050 kip/in)
    defl_res = calculate_beam_deflection(
        span_in=288.0,
        section=section,
        w_dead_kip_per_in=0.0833,
        w_live_kip_per_in=0.0500,
        support_condition="simple",
        sustained_live_ratio=0.20,
        sustained_months=60.0,
    )

    print("=" * 60)
    print(" SERVICEABILITY & CRACK CONTROL ANALYSIS")
    print("=" * 60)
    print(f"Gross Inertia Ig:            {Ig:.0f} in^4")
    print(f"Cracked Transformed Icr:     {Icr:.0f} in^4")
    print(f"Cracking Moment Mcr:         {Mcr:.1f} kip-in ({Mcr / 12:.1f} kip-ft)")
    print(f"Service Moment Ma:           {Ma:.1f} kip-in")
    print(f"Effective Inertia Ie (Bischoff): {Ie:.0f} in^4")
    print("-" * 60)
    print(f"Service Steel Stress fs:     {crack_res.steel_stress_ksi:.1f} ksi")
    print(f"Max Crack Spacing Allowed:   {crack_res.allowable_spacing:.1f} in o.c.")
    print(f"Provided Bar Spacing:        {crack_res.provided_spacing:.1f} in o.c.")
    print(f"Crack Control Status:        {crack_res.status}")
    print("-" * 60)
    print(f"Immediate Live Deflection:   {defl_res.immediate_live_deflection:.3f} in (Limit: {defl_res.limit_l_over_360:.3f} in)")
    print(f"Total Long-Term Deflection:  {defl_res.total_deflection:.3f} in (Limit: {defl_res.limit_l_over_240:.3f} in)")
    print(f"Overall Deflection Status:   {defl_res.status}")
    print("=" * 60)

if __name__ == "__main__":
    run_serviceability_example()
