"""
ACI 318 Code Factors & Reduction Factors Example.

Demonstrates:
1. Strength reduction factors (phi) for flexure, shear, torsion, and axial compression.
2. Whitney stress block depth factor (beta1) calculation for high-strength concrete.
3. Lightweight concrete modification factor (lambda).
4. Code comparison between ACI 318-19 and ACI 318-25.
"""

from aci318 import ACI318_19, ACI318_25, Concrete

def run_code_factors_example():
    code_19 = ACI318_19()
    code_25 = ACI318_25()

    fc_values = [3.0, 4.0, 6.0, 8.0, 10.0, 12.0]

    header_col1 = "f'c (ksi)"
    print("=" * 65)
    print(" WHITNEY STRESS BLOCK FACTOR beta_1 vs CONCRETE STRENGTH f'c")
    print("=" * 65)
    print(f"{header_col1:<15} {'beta_1 (ACI 318-19)':<25} {'beta_1 (ACI 318-25)':<25}")
    print("-" * 65)

    for fc in fc_values:
        b1_19 = code_19.get_beta_1(fc)
        b1_25 = code_25.get_beta_1(fc)
        print(f"{fc:<15.1f} {b1_19:<25.4f} {b1_25:<25.4f}")

    print("\n" + "=" * 65)
    print(" STRENGTH REDUCTION FACTORS phi (ACI 318-19)")
    print("=" * 65)
    print(f"Flexure (Tension-controlled, eps_t >= 0.005):     phi = {code_19.get_phi_flexure(strain_t=0.005):.3f}")
    print(f"Flexure (Compression-controlled, eps_t <= 0.002): phi = {code_19.get_phi_flexure(strain_t=0.002):.3f}")
    print(f"Shear & Torsion:                                  phi = {code_19.get_phi_shear():.3f}")
    print(f"Axial Compression (Tied Column):                  phi = {code_19.get_phi_axial(compression=True, spiral=False):.3f}")
    print(f"Axial Compression (Spiral Column):                phi = {code_19.get_phi_axial(compression=True, spiral=True):.3f}")

    # Lightweight concrete lambda factor
    nw_conc = Concrete(fc=4.0, concrete_type="normalweight", density=145.0)
    lw_conc = Concrete(fc=4.0, concrete_type="sand_lightweight", density=115.0)

    print("\n" + "=" * 65)
    print(" LIGHTWEIGHT CONCRETE MODIFICATION FACTOR lambda")
    print("=" * 65)
    print(f"Normalweight Concrete (145 pcf):    lambda = {code_19.get_lambda_(nw_conc):.2f}")
    print(f"Sand-Lightweight Concrete (115 pcf): lambda = {code_19.get_lambda_(lw_conc):.2f}")
    print("=" * 65)

if __name__ == "__main__":
    run_code_factors_example()
