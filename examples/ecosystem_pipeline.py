"""
Full Structural Engineering Ecosystem Pipeline Example.

Demonstrates end-to-end multi-package workflow for a 2-Story 3D RC Space Frame:
1. Model & Geometry Definition (struct_core):
   - 2-story 3D frame (18 nodes, 12 columns, 14 beams, 6 fixed base supports).
2. Code Loading & ELF Seismic Procedure (struct_load):
   - DEAD (self-weight), SuperDead (10 kN/m), LIVE (4 kN/m).
   - ASCE 7-22 Equivalent Lateral Force (ELF) seismic distribution (EQ_X).
3. 3D Finite Element Analysis (fem3d):
   - Independent linear static solution for each primary load case.
   - ASCE 7 load combination superposition (struct_core.superpose_results).
4. Concrete Design & Detailing (aci318):
   - Automated conversion from metric SI (kN, m) to ACI 318 internal units.
   - Governing load combination enveloping.
   - Beam flexure & shear design, column biaxial P-M-M interaction, and footing design.
5. CAD Drawing & Detailing Generation (struct_draw):
   - Floor framing plan DXF, frame elevation DXF, and rebar detailing schedule DXF.

All output files are saved to `aci318/examples/output/`.
"""

from pathlib import Path
from typing import Dict, List, Tuple

from struct_core import (
    BeamElement,
    DistributedLoad,
    ElasticMaterial,
    LoadCase,
    MassSource,
    MassSourceFactor,
    Metadata,
    Node,
    Project,
    RectangularSection,
    StructuralModel,
    Support,
    Units,
)
from struct_core.analysis_result.superposition import superpose_results
from struct_load import LoadGenerator, SeismicParameters
from fem3d import Results
from fem3d.adapters import model_from_core, result_to_core
from aci318.adapters import design_from_core
from struct_draw import (
    DrawingUnit,
    SCALE_1_50,
    SCALE_1_100,
    draw_from_core,
    draw_frame_elevation_from_core,
    draw_framing_plan_from_core,
)


def build_rc_frame_model() -> Tuple[StructuralModel, List[int], List[int]]:
    """Build canonical 2-story 3D RC Space Frame model in struct_core (kN, m)."""
    x_coords = [0.0, 4.0, 10.0]  # 4m and 6m bays
    y_coords = [0.0, 5.0]        # 5m bay
    z_coords = [0.0, 3.5, 7.0]   # 3.5m story height

    model = StructuralModel(units="kN, m", story_elevations=[3.5, 7.0])

    # Material: C30 Concrete (E = 30 GPa, unit_weight = 24 kN/m^3)
    mat = ElasticMaterial(id="C30", E=30.0e6, nu=0.20, rho=2400.0, unit_weight=24.0)
    model.materials.append(mat)

    # Sections: Columns (300x400 mm) & Beams (250x400 mm)
    sec_col = RectangularSection(id="Col_300x400", b=0.30, h=0.40)
    sec_bm = RectangularSection(id="Beam_250x400", b=0.25, h=0.40)
    model.sections.extend([sec_col, sec_bm])

    # Nodes (18 total) and Supports (6 fixed at base)
    nid = 1
    node_grid = {}
    for z in z_coords:
        for y in y_coords:
            for x in x_coords:
                model.nodes.append(Node(id=nid, x=x, y=y, z=z))
                if z == 0.0:
                    model.supports.append(Support.fixed_3d(node_id=nid))
                node_grid[(x, y, z)] = nid
                nid += 1

    # 12 Columns (6 per story)
    elem_id = 1
    col_ids = []
    for story in range(2):
        z_bot, z_top = z_coords[story], z_coords[story + 1]
        for y in y_coords:
            for x in x_coords:
                model.elements.append(
                    BeamElement(
                        id=elem_id,
                        name=f"C{elem_id}",
                        start_node=node_grid[(x, y, z_bot)],
                        end_node=node_grid[(x, y, z_top)],
                        material_id=mat.id,
                        section_id=sec_col.id,
                        include_shear_deformation=True,
                    )
                )
                col_ids.append(elem_id)
                elem_id += 1

    # 14 Beams (7 per floor level)
    beam_ids = []
    for story in (1, 2):
        z = z_coords[story]
        # X-direction beams
        for y in y_coords:
            for bay in (0, 1):
                model.elements.append(
                    BeamElement(
                        id=elem_id,
                        name=f"B{elem_id}",
                        start_node=node_grid[(x_coords[bay], y, z)],
                        end_node=node_grid[(x_coords[bay + 1], y, z)],
                        material_id=mat.id,
                        section_id=sec_bm.id,
                        include_shear_deformation=True,
                    )
                )
                beam_ids.append(elem_id)
                elem_id += 1
        # Y-direction beams
        for x in x_coords:
            model.elements.append(
                BeamElement(
                    id=elem_id,
                    name=f"B{elem_id}",
                    start_node=node_grid[(x, y_coords[0], z)],
                    end_node=node_grid[(x, y_coords[1], z)],
                    material_id=mat.id,
                    section_id=sec_bm.id,
                    include_shear_deformation=True,
                )
            )
            beam_ids.append(elem_id)
            elem_id += 1

    return model, col_ids, beam_ids


def run_pipeline() -> Project:
    print("=" * 75)
    print(" 3D RC SPACE FRAME: FULL STRUCTURAL ENGINEERING ECOSYSTEM PIPELINE")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # 1. Structural Model & Geometry Definition (struct_core)
    # -------------------------------------------------------------------------
    model, col_ids, beam_ids = build_rc_frame_model()
    project = Project(
        model=model,
        metadata=Metadata(
            project_name="2Story_3D_RC_Space_Frame",
            units=Units(force="kN", length="m", time="s", mass="kg", temperature="C"),
        ),
    )
    print(f"[1/5] Model Created: {len(model.nodes)} Nodes, {len(model.elements)} Elements "
          f"({len(col_ids)} Columns, {len(beam_ids)} Beams, {len(model.supports)} Fixed Bases)")

    # -------------------------------------------------------------------------
    # 2. Gravity Loads & ASCE 7-22 ELF Seismic Loads (struct_load)
    # -------------------------------------------------------------------------
    # DEAD: Column self-weight (2.88 kN/m) + Beam self-weight (2.40 kN/m)
    dead_loads = (
        [DistributedLoad(element_id=eid, wz=-2.88) for eid in col_ids]
        + [DistributedLoad(element_id=eid, wz=-2.40) for eid in beam_ids]
    )
    model.load_cases.append(LoadCase(id="DEAD", name="Self-Weight", element_loads=dead_loads))

    # SuperDead = 10 kN/m on all beams
    sdl_loads = [DistributedLoad(element_id=eid, wz=-10.0) for eid in beam_ids]
    model.load_cases.append(LoadCase(id="SuperDead", name="Superimposed Dead", element_loads=sdl_loads))

    # LIVE = 4 kN/m on all beams
    live_loads = [DistributedLoad(element_id=eid, wz=-4.0) for eid in beam_ids]
    model.load_cases.append(LoadCase(id="LIVE", name="Live Load", element_loads=live_loads))

    # Effective Seismic Weight Mass Source: W = 1.0 * SelfMass + 1.0 * SuperDead + 0.25 * LIVE
    mass_source = MassSource(
        id="MS_ELF",
        include_element_mass=True,
        factors=[
            MassSourceFactor(load_case_id="SuperDead", factor=1.0),
            MassSourceFactor(load_case_id="LIVE", factor=0.25),
        ],
    )
    model.mass_source = mass_source

    # Apply ASCE 7-22 Equivalent Lateral Force (ELF) Seismic Procedure
    seismic_params = SeismicParameters(
        sds=1.00,
        sd1=0.40,
        s1=0.35,
        tl=8.0,
        r_factor=8.0,
        importance_factor=1.0,
        system_type="rc_smf",
        site_class="D",
        risk_category="I",
        method=2,
    )
    generator = LoadGenerator(units="kN, m")
    _, elf_result = generator.apply_lateral_seismic(
        model,
        params=seismic_params,
        direction="X",
        seismic_case_id="EQ_X",
        mass_source=mass_source,
    )
    print(f"[2/5] Loads Generated:")
    print(f"      • Primary Cases: {[lc.id for lc in model.load_cases]}")
    print(f"      • Seismic Weight W: {elf_result.total_weight:.1f} kN | Period Ta: {elf_result.ta:.3f} s")
    print(f"      • ELF Base Shear V: {elf_result.base_shear:.1f} kN (Cs = {elf_result.cs:.4f})")

    # -------------------------------------------------------------------------
    # 3. 3D Finite Element Analysis & Combination Superposition (fem3d)
    # -------------------------------------------------------------------------
    primary_cases = ["DEAD", "SuperDead", "LIVE", "EQ_X"]
    for cid in primary_cases:
        struct = model_from_core(model, load_case_id=cid)
        struct.solve()
        res = result_to_core(Results(struct))
        res.analysis_case_id = cid
        project.analysis_results[cid] = res

    # ASCE 7 Factored Load Combinations
    combinations = {
        "1.4D": {"DEAD": 1.4, "SuperDead": 1.4},
        "1.2D+1.6L": {"DEAD": 1.2, "SuperDead": 1.2, "LIVE": 1.6},
        "1.2D+1.0L+1.0EQ": {"DEAD": 1.2, "SuperDead": 1.2, "LIVE": 1.0, "EQ_X": 1.0},
        "0.9D-1.0EQ": {"DEAD": 0.9, "SuperDead": 0.9, "EQ_X": -1.0},
    }
    for combo_id, factors in combinations.items():
        project.analysis_results[combo_id] = superpose_results(
            case_results=project.analysis_results,
            factors=factors,
            output_case_id=combo_id,
        )

    print(f"[3/5] FEA Completed: 4 primary cases solved + {len(combinations)} ASCE 7 combinations superposed")

    # -------------------------------------------------------------------------
    # 4. Code Design & Detailing (aci318)
    # -------------------------------------------------------------------------
    design_res, detailing_res = design_from_core(project)
    project.design_results["ACI318_19"] = design_res
    project.detailing_results["ACI318_19"] = detailing_res

    # Extract governing beam, column, and foundation metrics
    beam_dcrs = [e.governing_dcr for e in design_res.element_results.values() if e.member_type == "beam"]
    col_dcrs = [e.governing_dcr for e in design_res.element_results.values() if e.member_type == "column"]
    ftg_dcrs = [e.governing_dcr for e in design_res.element_results.values() if e.member_type == "footing"]

    print(f"[4/5] ACI 318-19 Design Summary:")
    print(f"      • Overall Status: {'PASSED' if design_res.passed else 'FAILED'} (Governing DCR = {design_res.governing_dcr:.3f})")
    print(f"      • Beams Designed: {len(beam_dcrs)} | Max Beam DCR: {max(beam_dcrs, default=0.0):.3f}")
    print(f"      • Columns Designed (Biaxial P-M-M): {len(col_dcrs)} | Max Column DCR: {max(col_dcrs, default=0.0):.3f}")
    print(f"      • Spread Footings Sized: {len(ftg_dcrs)} | Max Bearing/Punching DCR: {max(ftg_dcrs, default=0.0):.3f}")

    # -------------------------------------------------------------------------
    # 5. Engineering Drawing Generation (struct_draw)
    # -------------------------------------------------------------------------
    output_dir = Path(__file__).resolve().parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    plan_path = output_dir / "story1_framing_plan.dxf"
    draw_framing_plan_from_core(
        project,
        story_level=3.5,
        title="FIRST FLOOR FRAMING PLAN (Z = 3.5m)",
        unit=DrawingUnit.MM,
        scale=SCALE_1_100,
        output_path=plan_path,
    )

    elev_path = output_dir / "frame_elevation_gridA.dxf"
    draw_frame_elevation_from_core(
        project,
        grid_line=0.0,
        title="FRAME ELEVATION - GRID A (Y = 0.0m)",
        unit=DrawingUnit.MM,
        scale=SCALE_1_50,
        output_path=elev_path,
    )

    detailing_path = output_dir / "reinforcement_details.dxf"
    draw_from_core(
        project,
        scale=SCALE_1_50,
        output_path=detailing_path,
    )

    print(f"[5/5] CAD Drawings Exported to '{output_dir.relative_to(Path.cwd())}':")
    print(f"      1. {plan_path.name} (General Floor Framing Plan)")
    print(f"      2. {elev_path.name} (Frame Elevation View)")
    print(f"      3. {detailing_path.name} (Reinforcement Details & Bar Schedule)")
    print("=" * 75)
    print("PIPELINE COMPLETED SUCCESSFULLY (0 Errors)")
    print("=" * 75)

    return project


if __name__ == "__main__":
    run_pipeline()
