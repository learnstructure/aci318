"""
Continuous Wall Strip Footing and Two-Column Combined Footing Design Example.

Demonstrates:
1. StripFooting design for continuous load-bearing masonry/concrete walls.
2. Checking allowable soil bearing, one-way shear (with size effect), and transverse flexure.
3. CombinedFooting coordinator sizing length and width to align centroid with resultant column load.
4. Evaluating punching shear at two columns, one-way beam shear, and zero-shear longitudinal flexure.
"""

from aci318 import (
    ACI318_19,
    CombinedFooting,
    Concrete,
    LoadEffects,
    Steel,
    StripFooting,
)


def run_foundations_example():
    code = ACI318_19()
    concrete = Concrete(fc=4.0)
    steel = Steel(fy=60.0)

    print("=" * 65)
    print(" 1. CONTINUOUS WALL STRIP FOOTING DESIGN")
    print("=" * 65)

    # 4.0-ft wide strip footing supporting a 10-in concrete wall
    # Factored load: Pu = 12.0 kip/ft of wall length
    strip = StripFooting(
        width=4.0,
        thickness=14.0,
        wall_thickness=10.0,
        concrete=concrete,
        steel=steel,
        code=code,
        allowable_q=4.0,
        cover=3.0,
        transverse_bar_size="#5",
        longitudinal_bar_size="#4",
        member_id="STRIP-W101",
    )

    strip_res = strip.design(LoadEffects(Pu=12.0))

    print(f"Footing Width:               {strip_res.width:.1f} ft")
    print(f"Footing Thickness:           {strip_res.thickness:.1f} in")
    print(f"Supported Wall Thickness:    {strip_res.wall_thickness:.1f} in")
    print(f"Overall Status:              {strip_res.status}")
    print(f"Max Soil Bearing Pressure:   {strip_res.max_bearing_pressure:.2f} ksf (Allowable: {strip_res.allowable_bearing_capacity:.2f} ksf)")
    print(f"One-Way Shear DCR:           {strip_res.one_way_shear.demand_capacity_ratio:.2f} ({strip_res.one_way_shear.status})")
    print(f"Transverse Bottom Rebar:     #{strip_res.transverse_bar_size.replace('#','')} @ {strip_res.transverse_bar_spacing:.1f} in o.c.")
    print(f"Longitudinal Rebar Count:    {strip_res.longitudinal_bar_count} #{strip_res.longitudinal_bar_size.replace('#','')}")

    print("\n" + "=" * 65)
    print(" 2. TWO-COLUMN COMBINED FOOTING COORDINATOR")
    print("=" * 65)

    # Two columns spaced at 14 ft center-to-center
    # Col 1: 18x18 in, P1 = 200 kips, cantilever = 2.0 ft
    # Col 2: 20x20 in, P2 = 300 kips
    comb = CombinedFooting(
        column_spacing_ft=14.0,
        col1_c1=18.0,
        col1_c2=18.0,
        col2_c1=20.0,
        col2_c2=20.0,
        concrete=concrete,
        steel=steel,
        code=code,
        allowable_q=5.0,
        cantilever_col1_ft=2.0,
        thickness=28.0,
        bar_size="#8",
        member_id="COMB-F101",
    )

    comb_res = comb.design(p1_kip=200.0, p2_kip=300.0)

    print(f"Footing Length L:            {comb_res.length:.1f} ft")
    print(f"Footing Width B:             {comb_res.width:.1f} ft")
    print(f"Footing Thickness H:         {comb_res.thickness:.1f} in")
    print(f"Uniform Soil Pressure:       {comb_res.soil_pressure:.2f} ksf (Allowable: {comb_res.allowable_pressure:.2f} ksf)")
    print(f"Overall Status:              {comb_res.status}")
    print(f"Punching Shear Col 1 DCR:    {comb_res.punching_shear_col1.demand_capacity_ratio:.2f} ({comb_res.punching_shear_col1.status})")
    print(f"Punching Shear Col 2 DCR:    {comb_res.punching_shear_col2.demand_capacity_ratio:.2f} ({comb_res.punching_shear_col2.status})")
    print(f"Critical One-Way Shear DCR:  {comb_res.one_way_shear.demand_capacity_ratio:.2f} ({comb_res.one_way_shear.status})")
    print(f"Top Longitudinal Bars:       {comb_res.top_steel_bars}")
    print(f"Bottom Longitudinal Bars:    {comb_res.bottom_steel_bars}")
    print("=" * 65)


if __name__ == "__main__":
    run_foundations_example()
