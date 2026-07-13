# aci318 - Python Library for Reinforced Concrete Design

A professional, modular Python library that implements reinforced concrete design according to ACI 318.

## Project Structure

This project follows a highly modular architecture where each package component has a single responsibility:

* `codes/`: Abstraction layers for ACI 318 code versions (e.g., ACI 318-19, ACI 318-25).
* `loads/`: Standardized load action contracts (`LoadEffects` dataclass).
* `materials/`: Pure material models (`Concrete`, `Steel`).
* `sections/`: Geometric section properties (area, centroid, moment of inertia).
* `database/`: Static lookup tables for rebar sizes, material grades, etc.
* `validators/`: Input validation logic.
* `strength/`: The computational core containing flexure, shear, torsion, axial, interaction, and development engines.
* `serviceability/`: Deflection, cracking, and vibration checks.
* `members/`: User-facing component coordinators (e.g., Beam, Column, Slab, Wall).
* `foundations/`: Footing and pile cap designers.
* `detailing/`: Reinforcement spacing, layout, and detailing helper routines.
* `results/`: Dataclasses storing results returned by computational engines.
* `visualization/`: Plotting and section display utilities.
* `reports/`: HTML/Markdown generation tools.
* `utils/`: Reusable units conversion, exceptions, and constants.

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

## Running Tests

```bash
pytest
```
