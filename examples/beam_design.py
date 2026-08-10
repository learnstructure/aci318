"""
Rectangular Beam Design and Verification Example.

Demonstrates:
1. Checking an existing reinforced concrete beam section under flexure and shear.
2. Automatically designing longitudinal flexural rebar and transverse stirrups.
3. Generating a formatted ASCII text design report.
"""

from aci318 import (
    ACI318_19,
    Beam,
    BeamTextReport,
    Concrete,
    LoadEffects,
    RectangleSection,
    Steel,
)

def run_beam_example():
    # 1. Define materials and code
    concrete = Concrete(fc=4.0)  # f'c = 4 ksi
    steel = Steel(fy=60.0)      # fy = 60 ksi
    code = ACI318_19()

    # 2. Section geometry & loads
    section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
    loads = LoadEffects(Mu=2500.0, Vu=35.0)  # Mu = 2500 kip-in, Vu = 35 kips

    # 3. Check existing section with 4 #8 bars (As = 3.16 in²)
    section.add_rebar_layer(num_bars=4, bar_size="#8", depth=21.5, steel=steel)
    beam_check = Beam(section=section, code=code)
    check_result = beam_check.check(loads)

    print("=" * 60)
    print(" 1. EXISTING BEAM CHECK")
    print("=" * 60)
    print(f"Overall Status: {check_result.status}")
    print(f"Flexural Capacity φMn: {check_result.flexure.phi_mn:.1f} kip-in (Demand: {loads.Mu:.1f})")
    print(f"Shear Capacity    φVn: {check_result.shear.phi_vn:.1f} kips   (Demand: {loads.Vu:.1f})")
    print(f"Flexural DCR:     {check_result.flexure.demand_capacity_ratio:.2f}")
    print(f"Shear DCR:        {check_result.shear.demand_capacity_ratio:.2f}")

    # 4. Automated design on an unreinforced section
    clean_section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
    beam_designer = Beam(
        section=clean_section,
        code=code,
        stirrup_bar_size="#3",
        stirrup_legs=2,
        fy_shear=60.0,
    )

    design_result = beam_designer.design(loads, fy_flexure=60.0)

    print("\n" + "=" * 60)
    print(" 2. AUTOMATED REINFORCEMENT DESIGN")
    print("=" * 60)
    print(f"Design Status:           {design_result.status}")
    print(f"Required Flexural Steel: {design_result.required_flexure_As:.3f} in²")
    print(f"Provided Flexural Steel: {design_result.provided_flexure_As:.3f} in²")
    print(f"Suggested Bar Layout:    {design_result.suggested_bars}")
    print(f"Stirrup Spacing:         {design_result.required_shear_spacing:.1f} in")

    # 5. Print full ASCII engineering report
    print("\n" + "=" * 60)
    print(" 3. ASCII TEXT REPORT SUMMARY")
    print("=" * 60)
    report = BeamTextReport(clean_section, loads, design_result)
    report.print_to_console()

if __name__ == "__main__":
    run_beam_example()
