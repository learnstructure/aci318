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
  - **Beams:** Rectangular, T-Beam/Flanged, and Circular cross-sections under flexure, shear, and torsion. `Beam.design` accepts only tension-controlled layouts (ACI 318 §9.3.3.1, $\varepsilon_t \ge \varepsilon_{ty} + 0.003$) and, where $T_u > \phi T_{th}$, adds the longitudinal torsion steel $A_\ell$ (half per face) and sizes every outer stirrup leg for $A_v/(n s) + A_t/s$ (§9.5.4, §22.7).
  - **Columns:** Compression/tension axial capacity, P-M interaction diagrams by strain compatibility (bars inside the stress block displace concrete, $P_{n,\max}$ cut-off), ACI 318-25 §21.2.2.3 $\phi$ limit between $0.10 f'_c A_g$ and $P_{n,bal}$, ties/spirals, symmetric perimeter bar patterns (`RectangleSection.setup_perimeter_bar_pattern`), and **Biaxial P-M2-M3 Interaction** (Bresler Reciprocal Load Method §10.5.2 & Parme / Bresler Load Contour Method). `Column.design` accepts a sequence of concurrent load sets and reports the governing one.
  - **Slabs:** One-way flexural design and minimum shrinkage/temperature reinforcement.
  - **Walls:** In-plane shear, flexure, and axial capacity checks.
  - **Foundations:**
    - `IsolatedFooting`: Spread footing design with the allowable soil bearing pressure checked under service-level loads (`design(loads, service_loads=...)`, §13.3.1.1 with R13.2.6.1; `size_isolated_footing` sizes the base area for them), strength for the factored loads: 1-way shear, 2-way punching shear (with size effect $\lambda_s$ and the moment-transfer stress $\gamma_v M_{sc}$ of §8.4.4.2.3 about both axes), and orthogonal flexural reinforcement.
    - `StripFooting`: Continuous wall footing designer per linear foot of wall length, checking bearing capacity, one-way shear at distance $d$ from wall face, and transverse/longitudinal steel.
    - `CombinedFooting`: Two-column combined rectangular footing coordinator aligning footing centroid with resultant load, evaluating punching shear at both columns, critical one-way beam shear, and zero-shear longitudinal flexure.
    - `PileCap`: Multi-pile cap foundation coordinator evaluating individual pile reactions under combined P-M-M, two-way punching shear around column and individual piles, one-way beam shear, and orthogonal flexural reinforcement.
    - `RaftFoundation`: Mat / raft foundation coordinator evaluating soil bearing pressure with kern/lift-off checks, two-way column punching shear, one-way strip shear, and top/bottom two-way flexural reinforcement.
- **Serviceability & Deflection Analysis:**
  - Cracked transformed section inertia $I_{cr}$ solving neutral axis depth $kd$.
  - Bischoff effective moment of inertia $I_e$ (ACI 318-19 Eq. 24.2.3.5a).
  - Time-dependent deflection multiplier $\lambda_\Delta = \xi / (1 + 50\rho')$ (ACI 318-19 §24.2.4.1).
  - Multi-condition deflection solver (`calculate_beam_deflection`) evaluating immediate live and total long-term deflections against ACI 318 Table 24.2.2 limits ($L/360, L/240$).
  - Crack control verification (`verify_crack_control`) checking bar spacing against ACI 318-19 §24.3.2 with service steel stress calculation.
- **Strength Engines:** Independent, modular engines for flexure, shear, torsion, axial, P-M interaction, development length, and lap splices.
  - Standard hook development length $l_{dh}$ per ACI 318-25 §25.4.3.1, $f_y \psi_e \psi_s \psi_{cc} \psi_r d_b / 50\lambda\sqrt{f'_c}$ (psi), as printed in the inch-pound edition (`references/ACI-318-25- US unit.pdf`). The SI coefficient (21) printed in ACI 318M-25 is a misprint.
  - Lightweight factor $\lambda$ from aggregate composition or equilibrium density (Table 19.2.4.1).
  - Table 20.2.2.4 limits: $f_y \le 80$ ksi in $P_o$ and $A_{s,min}$; $f_{yt} \le 60$ ksi for shear and torsion.
- **Slenderness (`aci318.strength.slenderness`):** ACI 318-25 §6.6.4 stability index $Q$, sway magnifier $\delta_s$ (≤ 1.5 for Eq. (a)), $(EI)_{eff}$, $P_c$, $C_m$, member magnifier $\delta$, and $M_{2,min}$. `struct_agent` applies them to analysis results.
- **Moment frames (`aci318.seismic`):** ACI 318-25 Chapter 18 checks for special (§18.6–18.8), intermediate (§18.4) and ordinary (§18.3) frames: beam and column dimension and steel limits, capacity-design shear from $M_{pr}$ or $M_n$ ($V_c = 0$ where §18.6.5.2 / §18.7.6.2.1 apply), hoop spacing and Table 18.7.5.4 confinement, strong-column/weak-beam $\Sigma M_{nc} \ge 1.2 \Sigma M_{nb}$, and joint shear. Every frame gets Chapter 15 joint shear (Table 15.5.2.1, §15.3.1 trigger). Not covered: circular columns and the §18.7.3.3 alternative.
- **Section Optimization:** `BeamSectionOptimizer` searches dimension grids to minimize total material cost ($/ft) balancing concrete volume and rebar weight.
- **Reinforcement Detailing:** Structured schemas for bar placements, stirrup/tie spacing, and clear covers.
- **Clear cover on the section:** `RectangleSection`, `CircularSection` and `TBeamSection` carry `cover` (in, default 1.5 in per Table 20.5.1.3.1 for members not exposed to weather or in contact with ground). Bar placement, beam effective depth ($d = h - c_c - d_{stirrup} - d_b/2$), column bar spacing, and the Chapter 18 confinement and capacity checks read it.
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
├── foundations/    # Foundation designers (IsolatedFooting, StripFooting, CombinedFooting, PileCap, RaftFoundation)
├── optimization/   # Material cost & dimension optimization engines
├── detailing/      # Rebar placement & layout schemas
├── reports/        # Text and Markdown calculation report generators
├── database/       # Standard rebar database (ASTM #3 through #18)
├── seismic/        # Chapter 18 moment-frame and Chapter 15 joint checks
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

- **Materials come from each member's section, nothing is assumed.** A designed section names its `ConcreteMaterial` (f'c, E, density for λ), its longitudinal and transverse `RebarMaterial` (fy and fyt, Es) and its clear `cover`; a missing one raises a `ValueError` listing every incomplete section. The values flow to flexure, shear, torsion, P–M interaction, joints and the Chapter 18 checks (capacity design with $1.25 f_y$, confinement with $f_{yt}$).
- **Footings** are designed only when `allowable_bearing_pressure` (model pressure unit), `footing_cover` (model length unit) and `service_analysis_results` (one result per service-level combination) are given: the base area for the allowable pressure under the service reactions, the footing for strength under the factored ones (§13.3.1.1, R13.2.6.1), with the concrete and bars of the column it carries.
- `DesignResult.inputs` records the materials, sections and foundation inputs the design used.

- **Columns** are checked against every load combination and station separately (`analysis_result_to_load_sets`), so each axial force is paired with its own moments; axial tension (solver convention, tension positive) becomes a negative $P_u$. Longitudinal steel is designed (`aci318.members.column_reinforcement`): the lightest layout of equal #6–#11 bars in a symmetric perimeter pattern, between 1 % $A_g$ and the maximum of §10.6.1.1 (8 %) or, for special moment frames, §18.7.4.1 (6 %), whose axial and P–M strength carry every load set. Each face's bar spacing is ≤ 14 in, so that with crossties $h_x \le 14$ in (§18.7.5.2(e)), and the clear spacing is ≥ max(1.5 in, 1.5 $d_b$) (§25.2.3). In special moment frames the bars of columns at joints failing strong-column/weak-beam (§18.7.3.2) are then raised until $\Sigma M_{nc} \ge 1.2\,\Sigma M_{nb}$ or the 6 % limit is reached (`aci318.seismic.strong_column`).
- **Beams** are designed for the envelope (`analysis_result_to_load_effects`) with the most tensile concurrent axial force.
- Beam ductility (§9.3.3.1) and torsion (§22.7) are reported as `code_checks` and count toward the governing DCR.
- **Frame checks:** the frame system comes from `Project.seismic_basis` (`rc_smf`, `rc_imf`, `rc_omf`; anything else is a gravity frame). Chapter 18 member checks go to each element's `code_checks`. Joint checks, plus the analysis checks carried by `AnalysisResult.code_checks` (slenderness, story drift, stability), go to `DesignResult.system_checks`. All of them enter the governing DCR. Joints of gravity frames with continuous beams use the factored-analysis moments (§15.4.2.1(a)); other joints use $M_n$ or $M_{pr}$.

```python
from aci318.adapters import design_from_core

# Reads the analysis forces and populates DesignResult and DetailingResult
design_res, detail_res = design_from_core(project, design_code="ACI 318-25")

# With footings: allowable soil pressure (model units, e.g. kPa) under service-level reactions
design_res, detail_res = design_from_core(
    project, design_code="ACI 318-25",
    allowable_bearing_pressure=150.0, footing_cover=0.075, service_analysis_results=[d_plus_l, d_plus_07e],
)
project.design_results["ACI318_25"] = design_res
project.detailing_results["ACI318_25"] = detail_res
```

See [`examples/ecosystem_pipeline.py`](examples/ecosystem_pipeline.py) for a complete multi-package engineering workflow connecting `struct_core` + `struct_load` (ASCE 7-22 ELF) + `fem3d` (3D FEA & combinations) + `aci318` (reinforced concrete design) + `struct_draw` (CAD DXF drawings).


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
