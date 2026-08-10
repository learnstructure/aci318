"""
Beam Cross-Section Cost Optimization Example.

Demonstrates:
1. Using BeamSectionOptimizer to search grid dimensions (b x h).
2. Calculating relative material costs ($/ft) combining concrete and rebar.
3. Selecting the optimal beam cross-section satisfying ACI 318 flexure & shear provisions.
"""

from aci318 import ACI318_19, BeamSectionOptimizer, LoadEffects

def run_optimization_example():
    code = ACI318_19()

    # Applied loads: Mu = 3200 kip-in (266.7 kip-ft), Vu = 45 kips
    loads = LoadEffects(Mu=3200.0, Vu=45.0)

    # Initialize optimizer with material unit costs:
    # Concrete = $135 / yd³
    # Steel = $1.10 / lb
    optimizer = BeamSectionOptimizer(
        code=code,
        fc=4.0,                 # f'c = 4 ksi
        fy=60.0,                # fy = 60 ksi
        concrete_cost_yd3=135.0,# $/yd³
        steel_cost_lb=1.10,     # $/lb
    )

    print("=" * 60)
    print(" BEAM SECTION COST OPTIMIZATION GRID SEARCH")
    print("=" * 60)
    print(f"Applied Loads: Mu = {loads.Mu:.0f} kip-in, Vu = {loads.Vu:.0f} kips\n")

    # Search width b from 10" to 18" (step 2") and height h from 18" to 32" (step 2")
    opt_result = optimizer.optimize(
        loads=loads,
        min_b=10.0, max_b=18.0, step_b=2.0,
        min_h=18.0, max_h=32.0, step_h=2.0,
    )

    print(f"Optimal Section Width (b):  {opt_result.width:.0f} in")
    print(f"Optimal Section Height (h): {opt_result.height:.0f} in")
    print(f"Concrete Cost per ft:       ${opt_result.concrete_cost_per_ft:.2f}")
    print(f"Steel Cost per ft:          ${opt_result.steel_cost_per_ft:.2f}")
    print(f"Total Material Cost per ft: ${opt_result.cost_per_ft:.2f}")
    print("=" * 60)

if __name__ == "__main__":
    run_optimization_example()
