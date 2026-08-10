"""
Calculation Reports & Rebar Detailing Schemas Example.

Demonstrates:
1. Generating publication-ready Markdown calculation reports.
2. Constructing structured, exportable detailing schemas for CAD/BIM integrations.
"""

import dataclasses
import json
from aci318 import (
    ACI318_19,
    BarPlacement,
    Beam,
    Concrete,
    LoadEffects,
    MarkdownReport,
    RectangleSection,
    Steel,
    create_beam_detail_from_design_result,
    create_column_detail,
)

def run_reports_and_detailing():
    code = ACI318_19()
    concrete = Concrete(fc=4.0)
    steel = Steel(fy=60.0)

    # 1. GENERATE MARKDOWN REPORT FOR A DESIGNED BEAM
    section = RectangleSection(b=14.0, h=26.0, concrete=concrete)
    loads = LoadEffects(Mu=3400.0, Vu=42.0)

    beam = Beam(section=section, code=code, stirrup_bar_size="#4", stirrup_legs=2)
    design_result = beam.design(loads)

    markdown_gen = MarkdownReport(
        title="Girder G-101 (Level 2) ACI 318-19 Design Summary",
        section=section,
        loads=loads,
        result=design_result,
        code_name="ACI 318-19",
    )

    md_content = markdown_gen.generate()

    print("=" * 60)
    print(" 1. GENERATED MARKDOWN REPORT PREVIEW (First 20 lines)")
    print("=" * 60)
    print("\n".join(md_content.split("\n")[:20]))

    # 2. GENERATE STRUCTURED REINFORCEMENT DETAILING SCHEMAS
    print("\n" + "=" * 60)
    print(" 2. REINFORCEMENT DETAILING SCHEMAS (JSON Export)")
    print("=" * 60)

    # Beam detail schema from design result
    beam_detail = create_beam_detail_from_design_result(
        design_result=design_result,
        member_id="G-101",
    )
    print(f"\nBeam Detailing Object (ID: {beam_detail.id}):")
    print(f"Total Bar Placements: {len(beam_detail.bars)}")
    for bar in beam_detail.bars:
        print(f" - [{bar.location.upper()}] {bar.count} {bar.bar_size} bars, Cover: {bar.cover}\", Spacing: {bar.spacing}\"")

    # Column detail schema creation
    col_longitudinal = [
        BarPlacement(id="c-corner", bar_size="#9", count=4, location="corner", cover=1.5),
        BarPlacement(id="c-middle", bar_size="#8", count=4, location="face", cover=1.5),
    ]
    col_ties = [
        BarPlacement(id="c-tie", bar_size="#4", count=1, location="tie", spacing=12.0, cover=1.5),
    ]
    col_detail = create_column_detail(member_id="COL-C1", longitudinal_bars=col_longitudinal, ties=col_ties)

    print(f"\nColumn Detailing JSON Schema (ID: {col_detail.id}):")
    detail_dict = col_detail.model_dump() if hasattr(col_detail, "model_dump") else dataclasses.asdict(col_detail)
    print(json.dumps(detail_dict, indent=2))

if __name__ == "__main__":
    run_reports_and_detailing()
