"""
Unit Conversion & SI Metric Workflow Example.

Demonstrates:
1. Converting SI Metric inputs (mm, MPa, kN, kN-m) to US Customary units (in, ksi, kips, kip-in).
2. Designing a beam in US Customary computational units.
3. Converting design capacity results back to SI Metric (kN-m, kN).
"""

from aci318 import (
    ACI318_19,
    Beam,
    Concrete,
    LoadEffects,
    RectangleSection,
    Steel,
)
from aci318.utils.units import (
    convert_force,
    convert_length,
    convert_moment,
    convert_stress,
)

def run_unit_conversion_example():
    code = ACI318_19()

    # 1. SI Metric Inputs
    b_mm = 300.0        # Width = 300 mm
    h_mm = 600.0        # Height = 600 mm
    d_mm = 540.0        # Effective depth d = 540 mm
    As_mm2 = 1800.0     # Steel area = 1800 mm²
    fc_MPa = 30.0       # f'c = 30 MPa
    fy_MPa = 420.0      # fy = 420 MPa
    Mu_kNm = 310.0      # Factored Moment = 310 kN-m
    Vu_kN = 140.0       # Factored Shear = 140 kN

    # 2. Convert SI Metric -> US Customary
    b_in = convert_length(b_mm, "mm", "in")
    h_in = convert_length(h_mm, "mm", "in")
    d_in = convert_length(d_mm, "mm", "in")
    As_in2 = As_mm2 * (convert_length(1.0, "mm", "in") ** 2)
    fc_ksi = convert_stress(fc_MPa, "mpa", "ksi")
    fy_ksi = convert_stress(fy_MPa, "mpa", "ksi")
    Mu_kipin = convert_moment(Mu_kNm, "kn-m", "kip-in")
    Vu_kip = convert_force(Vu_kN, "kn", "kip")

    print("=" * 60)
    print(" 1. CONVERTED INPUT PARAMETERS (SI Metric -> US Customary)")
    print("=" * 60)
    print(f"Section Dimensions: {b_mm:.0f} x {h_mm:.0f} mm  -->  {b_in:.2f} x {h_in:.2f} in")
    print(f"Effective Depth d:  {d_mm:.0f} mm       -->  {d_in:.2f} in")
    print(f"Steel Area As:      {As_mm2:.0f} mm²      -->  {As_in2:.3f} in²")
    print(f"Concrete f'c:       {fc_MPa:.0f} MPa       -->  {fc_ksi:.2f} ksi")
    print(f"Steel fy:           {fy_MPa:.0f} MPa      -->  {fy_ksi:.2f} ksi")
    print(f"Applied Moment Mu:  {Mu_kNm:.0f} kN-m      -->  {Mu_kipin:.1f} kip-in")
    print(f"Applied Shear Vu:   {Vu_kN:.0f} kN        -->  {Vu_kip:.1f} kips")

    # 3. Perform Analysis in aci318
    concrete = Concrete(fc=fc_ksi)
    steel = Steel(fy=fy_ksi)
    section = RectangleSection(b=b_in, h=h_in, concrete=concrete)
    section.add_rebar_layer(area=As_in2, depth=d_in, steel=steel)

    loads = LoadEffects(Mu=Mu_kipin, Vu=Vu_kip)
    beam = Beam(section=section, code=code)
    result = beam.check(loads)

    # 4. Convert Results Back to SI Metric
    phi_Mn_kNm = convert_moment(result.flexure.phi_mn, "kip-in", "kn-m")
    phi_Vn_kN = convert_force(result.shear.phi_vn, "kip", "kn")

    print("\n" + "=" * 60)
    print(" 2. ANALYSIS RESULTS (US Customary -> SI Metric)")
    print("=" * 60)
    print(f"Flexural Capacity phi_Mn: {result.flexure.phi_mn:.1f} kip-in  -->  {phi_Mn_kNm:.1f} kN-m")
    print(f"Flexural Demand Mu:       {Mu_kipin:.1f} kip-in  -->  {Mu_kNm:.1f} kN-m")
    print(f"Flexural DCR:             {result.flexure.demand_capacity_ratio:.2f}")
    print("-" * 60)
    print(f"Shear Capacity phi_Vn:    {result.shear.phi_vn:.1f} kips    -->  {phi_Vn_kN:.1f} kN")
    print(f"Shear Demand Vu:          {Vu_kip:.1f} kips    -->  {Vu_kN:.1f} kN")
    print(f"Shear DCR:                {result.shear.demand_capacity_ratio:.2f}")

if __name__ == "__main__":
    run_unit_conversion_example()
