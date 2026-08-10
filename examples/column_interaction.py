"""
Column P-M Interaction Diagram & Axial Capacity Example.

Demonstrates:
1. Rectangular tied columns and Circular spiral columns.
2. Generating a full P-M (Axial Force vs Bending Moment) interaction envelope curve.
3. Checking axial compression limits (Pn_max) and shear ties/spirals.
"""

from aci318 import (
    ACI318_19,
    AxialStrength,
    CircularSection,
    Concrete,
    InteractionStrength,
    LoadEffects,
    RectangleSection,
    Steel,
)

def run_column_example():
    code = ACI318_19()
    concrete = Concrete(fc=5.0)  # f'c = 5 ksi
    steel = Steel(fy=60.0)      # fy = 60 ksi

    # 1. Rectangular Tied Column (16" x 16", 8 #8 bars)
    rect_sec = RectangleSection(b=16.0, h=16.0, concrete=concrete)
    # 3 bars top layer (depth 2.5"), 2 middle (depth 8.0"), 3 bottom (depth 13.5")
    rect_sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=2.5, steel=steel)
    rect_sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=8.0, steel=steel)
    rect_sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=13.5, steel=steel)

    rect_ast = sum(layer.area for layer in rect_sec.layers)
    rect_axial = AxialStrength(rect_sec, code, spiral=False)
    p_max_rect = rect_axial.check(LoadEffects(Pu=0.0))

    print("=" * 60)
    print(" 1. RECTANGULAR TIED COLUMN (16\" x 16\", 8 #8 bars)")
    print("=" * 60)
    print(f"Gross Area Ag:       {rect_sec.gross_area:.1f} in²")
    print(f"Steel Area Ast:      {rect_ast:.2f} in²")
    print(f"Steel Ratio ρg:      {rect_ast / rect_sec.gross_area * 100:.2f}%")
    print(f"Pure Axial P0:       {p_max_rect.pn_nominal:.1f} kips")
    print(f"Max Design φPn_max:  {p_max_rect.phi_pn_max:.1f} kips")

    # Generate P-M Interaction Curve
    pm_engine = InteractionStrength(rect_sec, code)
    pm_curve = pm_engine.generate_pm_diagram(num_points=11)

    print("\nP-M Interaction Diagram Points (φPn, φMn):")
    print(f"{'Point':<8} {'Axial φPn (kips)':<20} {'Moment φMn (kip-in)':<20}")
    print("-" * 50)
    for i, (phi_mn, phi_pn) in enumerate(pm_curve.phi_points):
        print(f"{i+1:<8} {phi_pn:<20.1f} {phi_mn:<20.1f}")

    # 2. Circular Spiral Column (D = 18", 6 #8 bars)
    circ_sec = CircularSection(D=18.0, concrete=concrete)
    circ_sec.setup_circular_bar_pattern(
        num_bars=6,
        bar_size="#8",
        cover=1.5,
        tie_bar_size="#3",
        steel=steel,
    )

    circ_ast = sum(layer.area for layer in circ_sec.layers)
    circ_axial = AxialStrength(circ_sec, code, spiral=True)
    p_max_circ = circ_axial.check(LoadEffects(Pu=0.0))

    print("\n" + "=" * 60)
    print(" 2. CIRCULAR SPIRAL COLUMN (D = 18\", 6 #8 bars)")
    print("=" * 60)
    print(f"Gross Area Ag:       {circ_sec.gross_area:.1f} in²")
    print(f"Steel Area Ast:      {circ_ast:.2f} in²")
    print(f"Pure Axial P0:       {p_max_circ.pn_nominal:.1f} kips")
    print(f"Max Design φPn_max:  {p_max_circ.phi_pn_max:.1f} kips (Spiral α = 0.85, φ = 0.75)")

if __name__ == "__main__":
    run_column_example()
