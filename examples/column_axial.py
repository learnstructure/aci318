"""
Column axial capacity example.
"""

from aci318 import ACI318_19, AxialStrength, Concrete, RectangleSection, Steel

concrete = Concrete(fc=5.0)
steel = Steel(fy=60.0)
section = RectangleSection(b=14.0, h=14.0, concrete=concrete)
section.add_rebar_layer(area=3.16, depth=2.5, steel=steel)
section.add_rebar_layer(area=3.16, depth=11.5, steel=steel)

code = ACI318_19()
Pu = 650.0
result = AxialStrength(section, code, spiral=False).check(type("Loads", (), {"Pu": Pu})())

Ag = section.gross_area
Ast = sum(layer.area for layer in section.layers)
rho = Ast / Ag

print("=" * 60)
print("  RECTANGULAR TIED COLUMN  —  ACI 318-19")
print("=" * 60)
print(f"\nGross Area  Ag  = {Ag:.1f} in²")
print(f"Steel Area  Ast = {Ast:.2f} in²")
print(f"Steel Ratio ρg  = {rho:.4f}  ({rho * 100:.2f}%)")
print(f"\nφ·Pn_max = {result.phi_pn_max:.1f} kip")
print(f"Pu       = {Pu:.1f} kip")
print(f"Status   = {result.status}")
print("=" * 60)
