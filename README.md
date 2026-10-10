# aci318 - Python Library for Reinforced Concrete Design

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![ACI Code](https://img.shields.io/badge/ACI%20318-19%20%7C%2025-green.svg)](https://www.concrete.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**aci318** is a professional, modular, type-safe Python engineering library for structural design and analysis of reinforced concrete elements in full compliance with the American Concrete Institute Building Code Requirements for Structural Concrete (**ACI 318-19** and **ACI 318-25**).

Designed with a clean single-responsibility architecture, `aci318` provides automated design calculations, demand-capacity ratio evaluations, cross-section optimization, rebar detailing schemas, and engineering calculation report generation.

---

## Key Features

- **Code Version Abstraction:** Seamless switching between code provisions (**ACI 318-19** and **ACI 318-25**).
- **Structural Members:**
  - **Beams:** Rectangular, T-Beam/Flanged, and Circular cross-sections under flexure, shear, and torsion.
  - **Columns:** Compression/tension axial capacity, P-M interaction diagrams, ties/spirals, and **Biaxial P-M2-M3 Interaction** (Bresler Reciprocal Load Method §10.5.2 & Parme / Bresler Load Contour Method).
  - **Slabs:** One-way flexural design and minimum shrinkage/temperature reinforcement.
  - **Walls:** In-plane shear, flexure, and axial capacity checks.
  - **Foundations:**
    - `IsolatedFooting`: Spread footing design with allowable soil bearing pressure checks, 1-way shear, 2-way punching shear (with size effect $\lambda_s$), and orthogonal flexural reinforcement.
    - `StripFooting`: Continuous wall footing designer per linear foot of wall length, checking bearing capacity, one-way shear at distance $d$ from wall face, and transverse/longitudinal steel.
    - `CombinedFooting`: Two-column combined rectangular footing coordinator aligning footing centroid with resultant load, evaluating punching shear at both columns, critical one-way beam shear, and zero-shear longitudinal flexure.
- **Serviceability & Deflection Analysis:**
  - Cracked transformed section inertia $I_{cr}$ solving neutral axis depth $kd$.
  - Bischoff effective moment of inertia $I_e$ (ACI 318-19 Eq. 24.2.3.5a).
  - Time-dependent deflection multiplier $\lambda_\Delta = \xi / (1 + 50\rho')$ (ACI 318-19 §24.2.4.1).
  - Multi-condition deflection solver (`calculate_beam_deflection`) evaluating immediate live and total long-term deflections against ACI 318 Table 24.2.2 limits ($L/360, L/240$).
  - Crack control verification (`verify_crack_control`) checking bar spacing against ACI 318-19 §24.3.2 with service steel stress calculation.
- **Strength Engines:** Independent, modular engines for flexure, shear, torsion, axial, P-M interaction, development length, and lap splices.
  - Rigorous standard hook development length $l_{dh}$ with lightweight factor $\lambda$ in denominator per ACI 318-19 §25.4.3.1.
- **Section Optimization:** `BeamSectionOptimizer` searches dimension grids to minimize total material cost ($/ft) balancing concrete volume and rebar weight.
- **Reinforcement Detailing:** Structured schemas for bar placements, stirrup/tie spacing, and clear covers.
- **Engineering Reports:** Clean ASCII text calculation summaries and publication-ready Markdown design reports.
- **Units & Utilities:** Built-in unit converters supporting US Customary (`in`, `ft`, `kip`, `ksi`) and Metric/SI (`mm`, `m`, `kN`, `MPa`).

---

## Architecture Overview

`aci318` follows a decoupled, layered architectural blueprint where each package component has a distinct responsibility:

```
aci318/
├── codes/          # Code provisions & strength reduction factor (phi) rules
├── materials/      # Pure material models (Concrete & Steel)
├── sections/       # Cross-sectional geometry (Rectangle, T-Beam, Circle)
├── loads/          # Standardized load contracts (LoadEffects dataclass)
├── strength/       # Core computational engines (Flexure, Shear, Torsion, Axial, Development)
├── members/        # High-level element coordinators (Beam, Column, Slab, Wall)
├── foundations/    # Foundation designers (IsolatedFooting, StripFooting, CombinedFooting)
├── optimization/   # Material cost & dimension optimization engines
├── detailing/      # Rebar placement & layout schemas
├── reports/        # Text and Markdown calculation report generators
├── database/       # Standard rebar database (ASTM #3 through #18)
├── results/        # Dataclasses storing demand/capacity calculations
├── serviceability/ # Crack width, deflection, and vibration evaluation
├── validators/     # Input & geometry sanity checks
└── utils/          # Unit conversion dispatchers and exceptions
```

### Design Principles

1. **Single Responsibility Principle (SRP):** Section geometries calculate geometric properties ($A_g$, $I_g$, centroid) without making assumptions about applied loads. Material objects track material properties ($f'_c$, $f_y$, $E_c$, $E_s$). Strength engines evaluate demand vs. capacity without tightly coupling to UI or report formats.
2. **Zero Hard External Dependencies:** Core computational routines run natively on Python's standard library with optional Pydantic / Pytest enhancements.
3. **Transparent Safety Factors:** All capacity calculations return explicit nominal capacity ($M_n$, $V_n$, $P_n$), strength reduction factors ($\phi$), design capacity ($\phi M_n$, $\phi V_n$, $\phi P_n$), and Demand-Capacity Ratios (DCR).

---

## Installation

```bash
# Clone repository or navigate to workspace
git clone https://github.com/your-org/aci318.git
cd aci318

# Install package in editable mode
pip install -e .
```

---

## Demonstration Example

Below is a complete end-to-end Python script demonstrating beam design, rebar detailing generation, section cost optimization, and Markdown report output:

```python
from aci318 import (
    ACI318_19,
    Beam,
    BeamSectionOptimizer,
    Concrete,
    LoadEffects,
    MarkdownReport,
    RectangleSection,
    Steel,
    create_beam_detail_from_design_result,
)

# 1. Define Materials & Applied Loads
concrete = Concrete(fc=4.0)  # f'c = 4.0 ksi
steel = Steel(fy=60.0)      # fy = 60.0 ksi
loads = LoadEffects(Mu=2500.0, Vu=30.0)  # Mu = 2500 kip-in, Vu = 30 kip

# 2. Perform Automatic Beam Design
section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
beam = Beam(
    section=section,
    code=ACI318_19(),
    stirrup_bar_size="#3",
    stirrup_legs=2,
    fy_shear=60.0,
)

design_result = beam.design(loads, fy_flexure=60.0)

print(f"=== BEAM DESIGN RESULTS ===")
print(f"Status:                   {design_result.status}")
print(f"Required Flexural Steel:  {design_result.required_flexure_As:.2f} in²")
print(f"Provided Flexural Steel:  {design_result.provided_flexure_As:.2f} in²")
print(f"Suggested Bar Layout:     {design_result.suggested_bars}")
print(f"Required Stirrup Spacing: {design_result.required_shear_spacing:.1f} in")
print()

# 3. Generate Detailing Schema
detail = create_beam_detail_from_design_result(
    design_result=design_result,
    member_id="B-101",
)
print(f"Detailing ID: {detail.id} with {len(detail.bars)} bar placements.")
print()

# 4. Optimize Beam Dimensions for Material Cost ($/ft)
optimizer = BeamSectionOptimizer(code=ACI318_19(), fc=4.0, fy=60.0)
opt_res = optimizer.optimize(
    loads=loads,
    min_b=10.0, max_b=18.0, step_b=2.0,
    min_h=18.0, max_h=30.0, step_h=2.0,
)

print(f"=== OPTIMAL BEAM SECTION ===")
print(f"Optimal Size: {opt_res.width:.0f}\" x {opt_res.height:.0f}\"")
print(f"Total Cost:   ${opt_res.cost_per_ft:.2f} / ft")
print(f"Concrete:     ${opt_res.concrete_cost_per_ft:.2f} / ft")
print(f"Steel:        ${opt_res.steel_cost_per_ft:.2f} / ft")
print()

# 5. Generate Markdown Design Report
report = MarkdownReport(
    title="Main Transfer Beam B-101 Calculation Report",
    section=section,
    loads=loads,
    result=design_result,
    code_name="ACI 318-19",
)
markdown_output = report.generate()
print("=== GENERATED REPORT PREVIEW (First 15 lines) ===")
print("\n".join(markdown_output.split("\n")[:15]))
```

---

## Ecosystem Integration with `struct_core`

`aci318` provides the `design_from_core` adapter function that reads a `struct_core.Project` or `AnalysisResult` (including governing force envelopes across multiple load combinations produced by `fem2d` / `fem3d`) and automatically runs code design checks and detailing generation:

```python
from aci318.adapters import design_from_core

# Reads enveloped analysis forces (max Pu, Mu, Vu) and populates DesignResult and DetailingResult
design_res, detail_res = design_from_core(project, design_code="ACI 318-19")
project.design_results["ACI318_19"] = design_res
project.detailing_results["ACI318_19"] = detail_res
```

---

## Running Test Suite

Run the full automated test suite to verify code compliance and strength engines:

```bash
conda activate structeng
pytest tests
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
