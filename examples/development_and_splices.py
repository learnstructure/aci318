"""
Development Length & Lap Splice Calculations Example.

Demonstrates:
1. Tension development length (ld) and compression development length (ldc).
2. Modification factors (top bar, epoxy coating, lightweight concrete, casting position).
3. Class A and Class B tension lap splice lengths.
"""

from aci318 import (
    ACI318_19,
    Concrete,
    Steel,
    calculate_development_length,
    design_splice,
)
from aci318.database import BAR_DATABASE

def run_development_example():
    code = ACI318_19()
    concrete = Concrete(fc=4.0)  # f'c = 4 ksi
    steel = Steel(fy=60.0)      # fy = 60 ksi

    bar_sizes = ["#4", "#6", "#8", "#10"]

    print("=" * 75)
    print(" ACI 318-19 REBAR DEVELOPMENT LENGTHS & LAP SPLICES (f'c = 4.0 ksi, fy = 60 ksi)")
    print("=" * 75)
    print(f"{'Bar':<6} {'db (in)':<10} {'Tension ld (in)':<18} {'Compress ldc (in)':<20} {'Class B Splice (in)':<20}")
    print("-" * 75)

    for bar in bar_sizes:
        db = BAR_DATABASE[bar]["diameter"]

        # Calculate development length
        ld_res = calculate_development_length(
            bar_diameter=db,
            steel=steel,
            concrete=concrete,
            code=code,
            is_top_bar=False,
            is_epoxy=False,
            is_lightweight=False,
        )

        # Calculate Class B tension lap splice
        splice_res = design_splice(
            bar_size=bar,
            steel=steel,
            concrete=concrete,
            code=code,
            splice_class="B",
        )

        print(f"{bar:<6} {db:<10.3f} {ld_res.ld_tension:<18.1f} {ld_res.ld_compression:<20.1f} {splice_res.splice_length:<20.1f}")

    print("\n" + "=" * 75)
    print(" TOP BAR EFFECT (More than 12 in of fresh concrete cast below bars)")
    print("=" * 75)

    db_no8 = BAR_DATABASE["#8"]["diameter"]
    ld_bottom = calculate_development_length(db_no8, steel, concrete, code, is_top_bar=False)
    ld_top = calculate_development_length(db_no8, steel, concrete, code, is_top_bar=True)

    print(f"#8 Bottom Bar Tension ld: {ld_bottom.ld_tension:.1f} in")
    print(f"#8 Top Bar Tension ld:    {ld_top.ld_tension:.1f} in (ψt = 1.3 factor applied)")
    print("=" * 75)

if __name__ == "__main__":
    run_development_example()
