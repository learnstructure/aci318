"""
Flanged T-Beam Design and Capacity Example.

Demonstrates:
1. Flanged T-Beam geometry configuration (web width b_w, flange width b_f, flange thickness h_f).
2. T-Beam flexural capacity analysis (neutral axis in flange vs web).
3. Shear capacity evaluation with stirrups.
"""

from aci318 import (
    ACI318_19,
    Concrete,
    FlexureStrength,
    LoadEffects,
    ShearStrength,
    Steel,
    TBeamSection,
)

def run_tbeam_example():
    code = ACI318_19()
    concrete = Concrete(fc=4.5)  # f'c = 4.5 ksi
    steel = Steel(fy=60.0)      # fy = 60 ksi

    # 1. Create T-Beam: b_w = 14", h = 28", h_f = 6", b_f = 48"
    t_section = TBeamSection(
        b_f=48.0,     # effective flange width b_f
        h_f=6.0,      # flange thickness h_f
        b_w=14.0,     # web width b_w
        h=28.0,       # overall height h
        concrete=concrete,
    )

    # 2. Add tension reinforcement (6 #9 bars = 6.00 in² at depth d = 25.0")
    t_section.add_rebar_layer(num_bars=6, bar_size="#9", depth=25.0, steel=steel)

    # 3. Analyze Flexural Strength
    loads = LoadEffects(Mu=6500.0, Vu=65.0)  # Mu = 6500 kip-in (541.7 kip-ft), Vu = 65 kips

    flexure_engine = FlexureStrength(t_section, code)
    flex_res = flexure_engine.check(loads)

    print("=" * 60)
    print(" FLANGED T-BEAM FLEXURAL CAPACITY")
    print("=" * 60)
    print(f"Gross Area Ag:       {t_section.gross_area:.1f} in^2")
    print(f"Flange Width b_f:    {t_section.b_f:.1f} in")
    print(f"Flange Thickness h_f:{t_section.h_f:.1f} in")
    print(f"Web Width b_w:       {t_section.b_w:.1f} in")
    print(f"Design Moment phi_Mn:{flex_res.phi_mn:.1f} kip-in ({flex_res.phi_mn / 12:.1f} kip-ft)")
    print(f"Applied Moment Mu:   {loads.Mu:.1f} kip-in")
    print(f"Flexural DCR:        {flex_res.demand_capacity_ratio:.2f}")

    # 4. Check Shear Capacity (#4 stirrups 2 legs = 0.40 in^2, s = 8.0 in)
    shear_engine = ShearStrength(
        t_section,
        code,
        av=0.40,
        s=8.0,
        fy_shear=60.0,
    )
    shear_res = shear_engine.check(loads)

    print("\n" + "=" * 60)
    print(" SHEAR CAPACITY (b_w = 14 in, #4 stirrups @ 8.0 in)")
    print("=" * 60)
    print(f"Concrete Shear phi_Vc: {0.75 * shear_res.vn_concrete:.1f} kips")
    print(f"Steel Shear phi_Vs:    {0.75 * shear_res.vn_steel:.1f} kips")
    print(f"Total Shear phi_Vn:    {shear_res.phi_vn:.1f} kips (Demand: {loads.Vu:.1f} kips)")
    print(f"Shear DCR:             {shear_res.demand_capacity_ratio:.2f}")
    print(f"Shear Status:          {shear_res.status}")

if __name__ == "__main__":
    run_tbeam_example()
