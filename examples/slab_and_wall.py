"""
One-Way Slab & Structural Concrete Wall Design Example.

Demonstrates:
1. One-way slab flexural design per foot of slab width (b = 12.0 in).
2. Minimum temperature & shrinkage reinforcement checking.
3. Structural concrete shear wall flexure and shear verification.
"""

from aci318 import (
    ACI318_19,
    Concrete,
    LoadEffects,
    Slab,
    Wall,
)

def run_slab_and_wall_example():
    code = ACI318_19()
    concrete = Concrete(fc=4.0)  # f'c = 4 ksi

    # 1. ONE-WAY SLAB DESIGN
    # Slab thickness h = 7.0 in
    # Factored Moment Mu = 85.0 kip-in / ft width, Factored Shear Vu = 5.5 kips / ft width
    slab = Slab(
        thickness=7.0,
        concrete=concrete,
        code=code,
        member_id="SLAB-01",
        cover=0.75,
        bar_size="#4",
        fy=60.0,
    )

    slab_loads = LoadEffects(Mu=85.0, Vu=5.5)
    slab_res = slab.design(loads=slab_loads)

    print("=" * 60)
    print(" 1. ONE-WAY ELEVATED SLAB DESIGN (h = 7.0 in)")
    print("=" * 60)
    print(f"Slab Status:             {slab_res.status}")
    print(f"Required Flexural Steel: {slab_res.required_flexure_As:.3f} in^2/ft")
    print(f"Provided Flexural Steel: {slab_res.provided_flexure_As:.3f} in^2/ft")
    print(f"Temperature/Shrinkage As:{slab_res.temp_shrinkage_As:.3f} in^2/ft")
    print(f"Suggested Bar Spacing:   {slab_res.suggested_bar_spacing:.1f} in o.c. (#{slab_res.bar_size})")
    print(f"Shear Capacity phi_Vc:   {slab_res.shear.phi_vn:.1f} kips/ft (Demand: {slab_loads.Vu:.1f})")

    # 2. STRUCTURAL CONCRETE SHEAR WALL DESIGN
    # Wall thickness tw = 10.0 in, wall height Hw = 120 in (10 ft), wall length Lw = 144 in (12 ft)
    wall = Wall(
        thickness=10.0,
        height=120.0,
        length=144.0,
        concrete=concrete,
        code=code,
        member_id="WALL-W1",
        cover=0.75,
        bar_size="#4",
        fy=60.0,
    )

    # Loads per foot width of wall strip: Mu = 120 kip-in/ft, Vu = 10 kips/ft, Pu = 15 kips/ft
    wall_loads = LoadEffects(Mu=120.0, Vu=10.0, Pu=15.0)
    wall_res = wall.design(loads=wall_loads)

    print("\n" + "=" * 60)
    print(" 2. STRUCTURAL CONCRETE WALL DESIGN (tw = 10 in)")
    print("=" * 60)
    print(f"Overall Wall Status:     {wall_res.status}")
    print(f"Vertical Rebar Spacing:  {wall_res.vertical_bar_spacing:.1f} in o.c. (As = {wall_res.provided_vertical_As:.3f} in^2/ft)")
    print(f"Horizontal Rebar Spacing:{wall_res.horizontal_bar_spacing:.1f} in o.c. (As = {wall_res.provided_horizontal_As:.3f} in^2/ft)")
    print(f"Shear Capacity phi_Vn:   {wall_res.shear.phi_vn:.1f} kips/ft (Demand: {wall_loads.Vu:.1f})")

if __name__ == "__main__":
    run_slab_and_wall_example()
