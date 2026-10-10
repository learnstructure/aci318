"""
Isolated Spread Footing Design Example.

Demonstrates:
1. Sizing an isolated square or rectangular spread footing.
2. Checking allowable net soil bearing pressure.
3. Evaluating one-way beam shear capacity at distance d from column face.
4. Evaluating two-way punching shear capacity at perimeter d/2 from column face.
5. Flexural design for required footing bottom reinforcement.
"""

from aci318 import (
    ACI318_19,
    Concrete,
    IsolatedFooting,
    IsolatedFootingDesignResult,
    LoadEffects,
    Steel,
)


def run_isolated_footing_example():
    code = ACI318_19()
    concrete = Concrete(fc=3.0)  # f'c = 3.0 ksi for footing
    steel = Steel(fy=60.0)      # fy = 60.0 ksi

    # Applied ultimate factored loads
    # Pu = 272 kips, Mu = 150 kip-in (or 12.5 kip-ft)
    loads = LoadEffects(Pu=272.0, Mu=150.0)

    # Footing dimensions: 8.0 ft x 8.0 ft x 24.0 in thick
    # Supporting a 16" x 16" square column
    footing = IsolatedFooting(
        length=8.0,            # L = 8.0 ft
        width=8.0,             # W = 8.0 ft
        thickness=24.0,        # H = 24.0 in
        col_c1=16.0,           # Column c1 = 16.0 in
        col_c2=16.0,           # Column c2 = 16.0 in
        concrete=concrete,
        steel=steel,
        code=code,
        allowable_q=5.0,       # Allowable soil bearing = 5.0 ksf
        bar_size="#6",
        member_id="FTG-101",
    )

    # Perform Footing Checks & Design
    res: IsolatedFootingDesignResult = footing.design(loads=loads)

    print("=" * 60)
    print(" ISOLATED SPREAD FOOTING DESIGN SUMMARY")
    print("=" * 60)
    print(f"Footing Plan Dimensions: {footing.length:.1f} ft x {footing.width:.1f} ft")
    print(f"Footing Thickness H:     {footing.thickness:.1f} in")
    print(f"Column Cross-Section:    {footing.col_c1:.0f}\" x {footing.col_c2:.0f}\"")
    print(f"Overall Design Status:   {res.status}")
    print("-" * 60)
    print(f"1. Soil Bearing Pressure:")
    print(f"   Max Soil Pressure:     {res.max_bearing_pressure:.2f} ksf")
    print(f"   Allowable Capacity:    {res.allowable_bearing_capacity:.2f} ksf")

    print(f"\n2. One-Way Beam Shear:")
    print(f"   Demand Vu1:            {res.one_way_shear.vn_concrete * res.one_way_shear.demand_capacity_ratio * res.one_way_shear.phi_vn / max(res.one_way_shear.vn_concrete, 1.0):.1f} kips")
    print(f"   Capacity phi_Vc1:      {res.one_way_shear.phi_vn:.1f} kips")
    print(f"   One-Way Shear Status:  {res.one_way_shear.status} (DCR = {res.one_way_shear.demand_capacity_ratio:.2f})")

    print(f"\n3. Two-Way Punching Shear:")
    print(f"   Capacity phi_Vc2:      {res.punching_shear.phi_vn:.1f} kips")
    print(f"   Punching Shear Status: {res.punching_shear.status} (DCR = {res.punching_shear.demand_capacity_ratio:.2f})")

    print(f"\n4. Flexural Bottom Reinforcement:")
    print(f"   Required Steel As_x:   {res.required_As_x:.2f} in^2")
    print(f"   Required Steel As_y:   {res.required_As_y:.2f} in^2")
    print("=" * 60)


if __name__ == "__main__":
    run_isolated_footing_example()
