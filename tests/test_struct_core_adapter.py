"""
Tests for aci318.adapters.struct_core_adapter.

These tests validate the conversion-only boundary: the adapter should convert
existing ACI 318 results into struct_core schemas, not execute design calculations
itself.
"""

import pytest

from struct_core import (
    AnalysisResult,
    BarLayout,
    BarSchedule,
    BeamElement,
    BeamSectionForce,
    ConcreteMaterial,
    DesignResult,
    DetailingResult,
    ElasticMaterial,
    ElementDesignResult,
    ElementDetailingResult,
    ElementResult,
    FlexureDesignResult,
    Node,
    Project,
    RebarMaterial,
    RectangularSection,
    ShearDesignResult,
    StructuralModel,
)
from aci318.adapters import design_from_core
from aci318.results.beam import BeamDesignResult
from aci318.results.flexure import FlexureResult
from aci318.results.shear import ShearResult


def test_design_from_core_rejects_missing_results():
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)
    mat = ConcreteMaterial(id="Conc", fc=27_600.0, E=30000000.0, rho=2400.0)
    rebar = RebarMaterial(id="G60", fy=414_000.0, E=2.0e8)
    sec = RectangularSection(id="B12x18", b=12.0, h=18.0, material_id="Conc", rebar_material_id="G60", transverse_rebar_material_id="G60", cover=0.04)
    elem = BeamElement(id=1, start_node=1, end_node=2, section_id="B12x18")

    model = StructuralModel(nodes=[node1, node2], materials=[mat, rebar], sections=[sec], elements=[elem], units="kip, in")

    with pytest.raises(ValueError, match="No precomputed aci318 design/detailing result"):
        design_from_core(model)


def test_design_from_core_rejects_model_without_units():
    """F14.4 regression: adapter rejects model without units instead of falling back to kN, m or kip, in."""
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)
    mat = ConcreteMaterial(id="Conc", fc=27_600.0, E=30000000.0, rho=2400.0)
    rebar = RebarMaterial(id="G60", fy=414_000.0, E=2.0e8)
    sec = RectangularSection(id="B12x18", b=12.0, h=18.0, material_id="Conc", rebar_material_id="G60", transverse_rebar_material_id="G60", cover=0.04)
    elem = BeamElement(id=1, start_node=1, end_node=2, section_id="B12x18")
    model = StructuralModel(nodes=[node1, node2], materials=[mat, rebar], sections=[sec], elements=[elem])
    with pytest.raises(ValueError, match="Units are required for ACI 318 design"):
        design_from_core(model)


def test_design_from_core_converts_existing_beam_results():
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)
    mat = ConcreteMaterial(id="Conc", fc=27_600.0, E=30000000.0, rho=2400.0)
    rebar = RebarMaterial(id="G60", fy=414_000.0, E=2.0e8)
    sec = RectangularSection(id="B12x18", b=12.0, h=18.0, material_id="Conc", rebar_material_id="G60", transverse_rebar_material_id="G60", cover=0.04)
    elem = BeamElement(id=1, start_node=1, end_node=2, section_id="B12x18")
    model = StructuralModel(nodes=[node1, node2], materials=[mat, rebar], sections=[sec], elements=[elem], units="kip, in")

    beam_result = BeamDesignResult(
        required_flexure_As=2.0,
        suggested_bars="3 #8",
        provided_flexure_As=2.3,
        required_shear_spacing=12.0,
        stirrup_bar_size="#3",
        stirrup_legs=2,
        status="Passed",
        messages=["beam design ok"],
        flexure=FlexureResult(
            required_steel=2.0,
            provided_steel=2.3,
            neutral_axis=3.5,
            steel_strain=0.009,
            phi_mn=2400.0,
            status="Passed",
            demand_capacity_ratio=0.8,
        ),
        shear=ShearResult(
            vn_concrete=20.0,
            vn_steel=30.0,
            phi_vn=37.5,
            required_spacing=12.0,
            status="Passed",
            demand_capacity_ratio=0.5,
        ),
    )

    design_res, detail_res = design_from_core(model, design_result={1: beam_result}, detailing_result={1: ElementDetailingResult(
        element_id=1,
        member_type="beam",
        bar_layout=BarLayout(),
        bar_schedule=BarSchedule(items=[], total_weight=0.0),
    )})

    assert isinstance(design_res, DesignResult)
    assert isinstance(detail_res, DetailingResult)
    assert 1 in design_res.element_results
    assert isinstance(design_res.element_results[1], ElementDesignResult)
    assert design_res.element_results[1].flexure.required_steel_area == 2.0
    assert detail_res.element_results[1].member_type == "beam"


def test_analysis_result_to_load_effects_converts_fields():
    # Solver axial force is tension positive; aci318 Pu is compression positive
    sf = BeamSectionForce(station=0.0, P=100.0, Vy=8.0, Mz=120.0)
    ar = AnalysisResult(analysis_case_id="A1", element_results={1: ElementResult(element_id=1, forces=[sf])})

    loads = __import__("aci318.adapters.struct_core_adapter", fromlist=["analysis_result_to_load_effects"]).analysis_result_to_load_effects(1, ar)

    assert loads is not None
    assert loads.Pu == -100.0
    assert loads.Vu == 8.0
    assert loads.Mu == 120.0


def test_load_sets_keep_axial_force_concurrent_with_moment():
    """Each combination's axial force is paired with its own moment (ACI 318 §22.4)."""
    from aci318.adapters.struct_core_adapter import analysis_result_to_load_sets
    from struct_core.analysis_result import envelope_results

    # Gravity combination: large compression, small moment. Seismic uplift: tension with a large moment.
    gravity = AnalysisResult(analysis_case_id="1.2D+1.6L", element_results={
        "C1": ElementResult(element_id="C1", forces=[BeamSectionForce(station=0.0, P=-300.0, Mz=20.0)])})
    uplift = AnalysisResult(analysis_case_id="0.7D-1.0E", element_results={
        "C1": ElementResult(element_id="C1", forces=[BeamSectionForce(station=0.0, P=40.0, Mz=150.0)])})
    env = envelope_results([gravity, uplift])

    sets = analysis_result_to_load_sets("C1", env)
    pairs = sorted((s.Pu, s.Mu) for s in sets)
    assert pairs == [(-40.0, 150.0), (300.0, 20.0)]  # never (300 compression, 150)


def test_design_from_core_with_project_units():
    from struct_core import Metadata, Units
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)  # 6.0 meters
    mat = ConcreteMaterial(id="Conc", fc=27_600.0, E=30000000.0, rho=2400.0)
    rebar = RebarMaterial(id="G60", fy=414_000.0, E=2.0e8)
    sec = RectangularSection(id="B300x500", b=0.30, h=0.50, material_id="Conc", rebar_material_id="G60", transverse_rebar_material_id="G60", cover=0.04)  # 0.30m x 0.50m
    elem = BeamElement(id=1, start_node=1, end_node=2, section_id="B300x500")
    model = StructuralModel(nodes=[node1, node2], materials=[mat, rebar], sections=[sec], elements=[elem])

    # Analysis result in SI (kN, kN-m)
    sf = BeamSectionForce(station=0.0, P=0.0, Vy=50.0, Mz=100.0)
    ar = AnalysisResult(analysis_case_id="A1", element_results={1: ElementResult(element_id=1, forces=[sf])})

    project = Project(
        model=model,
        analysis_results={"A1": ar},
        metadata=Metadata(project_name="MetricBeam", units=Units(force="kN", length="m", time="s", mass="kg", temperature="C")),
    )

    design_res, detail_res = design_from_core(project)
    assert 1 in design_res.element_results
    assert design_res.element_results[1].passed
    assert 1 in detail_res.element_results


def test_design_from_core_converts_isolated_footing_results():
    from aci318.adapters.struct_core_adapter import isolated_footing_result_to_core
    from aci318.results.footing import IsolatedFootingDesignResult
    from aci318.results.shear import ShearResult
    from aci318.results.flexure import FlexureResult

    shear_dummy = ShearResult(
        vn_concrete=60.0,
        vn_steel=0.0,
        phi_vn=45.0,
        required_spacing=0.0,
        status="Passed",
        demand_capacity_ratio=0.8,
    )
    flex_dummy = FlexureResult(
        required_steel=3.5,
        provided_steel=3.5,
        neutral_axis=2.0,
        steel_strain=0.005,
        phi_mn=200.0,
        status="Passed",
        demand_capacity_ratio=0.7,
    )
    ftg_result = IsolatedFootingDesignResult(
        length=8.0,
        width=8.0,
        thickness=20.0,
        max_bearing_pressure=3.5,
        allowable_bearing_capacity=4.0,
        one_way_shear=shear_dummy,
        punching_shear=shear_dummy,
        flexure_x=flex_dummy,
        flexure_y=flex_dummy,
        required_As_x=3.5,
        required_As_y=3.5,
        status="Passed",
    )

    elem_design, elem_detail = isolated_footing_result_to_core("F1", ftg_result)
    assert elem_design.element_id == "F1"
    assert elem_design.member_type == "footing"
    assert elem_design.passed is True
    assert elem_detail.element_id == "F1"


def test_analysis_result_biaxial_moments_and_metric_units():
    from aci318.adapters.struct_core_adapter import analysis_result_to_load_effects
    from struct_core import Units

    # 100 kN axial, Mz = 100 kN-m (major), My = 60 kN-m (minor), Vy = 40 kN, Vz = 25 kN
    sf = BeamSectionForce(station=0.0, P=100.0, Vy=40.0, Vz=25.0, Mz=100.0, My=60.0)
    ar = AnalysisResult(analysis_case_id="COMB1", element_results={1: ElementResult(element_id=1, forces=[sf])})

    units = Units(force="kN", length="m", time="s", mass="kg", temperature="C")
    loads = analysis_result_to_load_effects(1, ar, units=units)

    assert loads is not None
    # 100 kN tension * 0.22480894 = -22.48 kips (compression positive)
    assert pytest.approx(loads.Pu, rel=1e-3) == -22.481
    # 100 kN-m * 8.85074579 = 885.07 kip-in
    assert pytest.approx(loads.Mu2, rel=1e-3) == 885.075
    assert pytest.approx(loads.Mu, rel=1e-3) == 885.075
    # 60 kN-m * 8.85074579 = 531.04 kip-in
    assert pytest.approx(loads.Mu3, rel=1e-3) == 531.045
    # Vy = 40 kN * 0.22480894 = 8.992 kips
    assert pytest.approx(loads.Vu2, rel=1e-3) == 8.992
    # Vz = 25 kN * 0.22480894 = 5.620 kips
    assert pytest.approx(loads.Vu3, rel=1e-3) == 5.620


def test_design_from_core_multiple_load_combinations_envelope():
    from struct_core import Metadata, Units
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)  # 6.0 meters
    mat = ConcreteMaterial(id="Conc", fc=27_600.0, E=30000000.0, rho=2400.0)
    rebar = RebarMaterial(id="G60", fy=414_000.0, E=2.0e8)
    sec = RectangularSection(id="B300x500", b=0.30, h=0.50, material_id="Conc", rebar_material_id="G60", transverse_rebar_material_id="G60", cover=0.04)  # 0.30m x 0.50m
    elem = BeamElement(id=1, start_node=1, end_node=2, section_id="B300x500")
    model = StructuralModel(nodes=[node1, node2], materials=[mat, rebar], sections=[sec], elements=[elem])

    # Combo 1: lower moment
    sf1 = BeamSectionForce(station=0.0, P=0.0, Vy=30.0, Mz=60.0)
    ar1 = AnalysisResult(analysis_case_id="1.4D", element_results={1: ElementResult(element_id=1, forces=[sf1], max_moment=60.0)})

    # Combo 2: governing higher moment
    sf2 = BeamSectionForce(station=0.0, P=0.0, Vy=55.0, Mz=110.0)
    ar2 = AnalysisResult(analysis_case_id="1.2D+1.6L", element_results={1: ElementResult(element_id=1, forces=[sf2], max_moment=110.0)})

    project = Project(
        model=model,
        analysis_results={"1.4D": ar1, "1.2D+1.6L": ar2},
        metadata=Metadata(project_name="MultiComboBeam", units=Units(force="kN", length="m", time="s", mass="kg", temperature="C")),
    )

    # design_from_core should automatically envelope ar1 and ar2, designing against 110 kN-m
    design_res, detail_res = design_from_core(project)
    assert 1 in design_res.element_results
    assert design_res.element_results[1].passed
    # Check that the moment designed for was 110 kN-m * 8.85074579 kip-in/kN-m = 973.58 kip-in
    assert pytest.approx(design_res.element_results[1].flexure.mu, rel=1e-2) == 973.58





def test_column_schedule_counts_every_designed_bar():
    """The column bar schedule lists all longitudinal bars, not only those of the first layer."""
    from aci318.adapters.struct_core_adapter import column_result_to_core
    from aci318.codes.aci318_25 import ACI318_25
    from aci318.loads.load_effects import LoadEffects
    from aci318.materials.concrete import Concrete
    from aci318.materials.steel import Steel
    from aci318.members.column_reinforcement import design_longitudinal_reinforcement
    from aci318.sections.rectangle import RectangleSection

    section = RectangleSection(b=20.0, h=20.0, concrete=Concrete(fc=4.0))
    design = design_longitudinal_reinforcement(
        section, [LoadEffects(Pu=600.0, Mu2=5000.0)], ACI318_25(), Steel(fy=60.0), 0.06
    )
    _, detailing = column_result_to_core("C1", design.result, elem_len_in=144.0, b_in=20.0, h_in=20.0)
    verticals = next(item for item in detailing.bar_schedule.items if item.location.endswith("Verticals"))
    assert verticals.quantity == design.layout.num_bars > 8


def _frame_5ksi_grade75(**section_overrides):
    """kip-in portal leg + beam: f'c = 5 ksi, Grade 75 bars, Grade 60 ties, 2 in cover (none of the old defaults)."""
    from struct_core import Support
    from struct_core.analysis_result import NodeReaction, NodeResult

    rc = dict(material_id="C5", rebar_material_id="G75", transverse_rebar_material_id="G60", cover=2.0)
    rc.update(section_overrides)
    model = StructuralModel(
        units="kip, in",
        nodes=[Node(id=1, x=0, y=0), Node(id=2, x=0, y=144), Node(id=3, x=240, y=144)],
        materials=[ConcreteMaterial(id="C5", fc=5.0, E=57.0 * 5000 ** 0.5, unit_weight=150.0 / 1728000.0),
                   RebarMaterial(id="G75", fy=75.0, E=29000.0), RebarMaterial(id="G60", fy=60.0, E=29000.0)],
        sections=[RectangularSection(id="COL", b=16, h=16, **rc), RectangularSection(id="BM", b=12, h=24, **rc)],
        elements=[BeamElement(id="C1", start_node=1, end_node=2, section_id="COL"),
                  BeamElement(id="B1", start_node=2, end_node=3, section_id="BM")],
        supports=[Support(node_id=1, ux=True, uy=True, rz=True)],
    )
    factored = AnalysisResult(analysis_case_id="env", element_results={
        "B1": ElementResult(element_id="B1", forces=[BeamSectionForce(station=0, P=0, V2=40, M3=2400),
                                                     BeamSectionForce(station=240, P=0, V2=-40, M3=2400)]),
        "C1": ElementResult(element_id="C1", forces=[BeamSectionForce(station=0, P=-300, V2=5, M3=200),
                                                     BeamSectionForce(station=144, P=-300, V2=5, M3=200)])},
        node_results={1: NodeResult(node_id=1, reaction=NodeReaction(fx=5.0, fy=300.0, mz=200.0))})
    service = AnalysisResult(analysis_case_id="D+L",
                             node_results={1: NodeResult(node_id=1, reaction=NodeReaction(fx=3.5, fy=210.0, mz=140.0))})
    return Project(model=model, analysis_results={"env": factored}, units="kip, in"), factored, service


def test_design_takes_concrete_bars_and_cover_from_the_section():
    """Hand checks (ACI 318-25) at f'c = 5 ksi, fy = 75 ksi, 2 in cover: the old adapter used 4 ksi, 60 ksi, 1.5 in."""
    project, factored, _ = _frame_5ksi_grade75()
    design, _ = design_from_core(project, factored)

    beam = design.element_results["B1"].flexure
    assert beam.provided_steel_area == pytest.approx(1.80)                 # 3 #7
    d = 24.0 - 2.0 - 0.375 - 0.875 / 2.0                                    # h - cover - #3 stirrup - db/2
    a = 1.80 * 75.0 / (0.85 * 5.0 * 12.0)                                   # §22.2.2
    c = a / 0.80                                                            # beta1 = 0.80 at 5 ksi (Table 22.2.2.4.3)
    assert 0.003 * (d - c) / c >= 75.0 / 29000.0 + 0.003                    # tension-controlled: phi = 0.90
    assert beam.phi_mn == pytest.approx(0.90 * 1.80 * 75.0 * (d - a / 2.0), rel=1e-6)

    column = design.element_results["C1"]
    ast = column.flexure.provided_steel_area
    phi_pn_max = 0.80 * 0.65 * (0.85 * 5.0 * (16 * 16 - ast) + 75.0 * ast)  # §22.4.2, tied
    assert column.governing_dcr == pytest.approx(300.0 / phi_pn_max, rel=1e-3)

    recorded = {m.id: m for m in design.inputs.materials}
    assert (recorded["C5"].fc, recorded["G75"].fy, recorded["G60"].fy) == (5.0, 75.0, 60.0)
    assert design.inputs.allowable_bearing_pressure is None                 # no footing inputs: none designed
    assert "F1" not in design.element_results


def test_design_names_every_section_without_its_design_inputs():
    project, factored, _ = _frame_5ksi_grade75(transverse_rebar_material_id=None, cover=None)
    with pytest.raises(ValueError) as error:
        design_from_core(project, factored)
    message = str(error.value)
    assert "Section 'COL'" in message and "Section 'BM'" in message
    assert "no transverse rebar material" in message and "no clear cover" in message


def test_footing_base_area_from_service_loads_and_strength_from_factored_loads():
    """ACI 318-25 R13.2.6.1: allowable pressure with service-level reactions (210 kip, 140 kip-in), not the factored
    300 kip; a 9 ft square: q = 210/81 (1 + 6 e / 9), e = 140 / 12 / 210 ft."""
    project, factored, service = _frame_5ksi_grade75()
    design, _ = design_from_core(project, factored, allowable_bearing_pressure=3.0 / 144.0, footing_cover=3.0,
                                 service_analysis_results=[service])
    footing = design.element_results["F1"]
    e = 140.0 / 12.0 / 210.0
    q_service = 210.0 / 81.0 * (1.0 + 6.0 * e / 9.0)
    assert footing.governing_dcr == pytest.approx(q_service / 3.0, rel=1e-6)  # bearing governs
    assert design.inputs.allowable_bearing_pressure == pytest.approx(3.0 / 144.0)
    assert design.inputs.footing_cover == 3.0


def test_footing_checks_uplift_and_all_combination_reactions():
    """Signed vertical reaction is preserved (uplift Pu < 0 fails soil bearing) and all combination reactions are checked."""
    from struct_core.analysis_result import NodeReaction, NodeResult

    project, factored, service = _frame_5ksi_grade75()
    factored.node_results[1] = NodeResult(
        node_id=1,
        reaction=NodeReaction(fx=5.0, fy=300.0, mz=200.0),
        combination_reactions={
            "1.2D+1.6L": NodeReaction(fx=2.0, fy=300.0, mz=100.0),
            "0.9D+1.0E": NodeReaction(fx=15.0, fy=-20.0, mz=2500.0),
        },
    )
    service_uplift = AnalysisResult(
        analysis_case_id="0.6D+0.7E",
        node_results={1: NodeResult(node_id=1, reaction=NodeReaction(fx=10.0, fy=-10.0, mz=1500.0))},
    )
    design, detail = design_from_core(
        project, factored, allowable_bearing_pressure=3.0 / 144.0, footing_cover=3.0,
        service_analysis_results=[service, service_uplift],
    )
    footing = design.element_results["F1"]
    assert not footing.passed
    assert getattr(detail.element_results["F1"], "_cover_in", None) == 3.0
    assert footing.flexure.phi_mn > 1.0 and footing.shear.phi_vn > 1.0


def test_f4_results_self_describe_units_and_convert_project_units_skips():
    """F4: DesignResult and DetailingResult self-describe units as kip, in and lbf, in.
    convert_project_units skips converting them."""
    from struct_core import convert_project_units
    project, factored, _ = _frame_5ksi_grade75()
    design, detail = design_from_core(project, factored)
    project.design_results["D1"] = design
    project.detailing_results["D1"] = detail

    assert design.units is not None
    assert design.units.short_label == "kip, in"
    assert detail.units is not None
    assert detail.units.short_label == "lbf, in"
    assert detail.bar_system == "US"

    old_mu = design.element_results["B1"].flexure.mu
    old_cut_len = detail.element_results["B1"].bar_schedule.items[0].cut_length

    # Convert project units
    p2 = convert_project_units(project, "kip, ft")
    d2 = p2.design_results["D1"]
    det2 = p2.detailing_results["D1"]

    assert d2.units.short_label == "kip, in"
    assert d2.element_results["B1"].flexure.mu == old_mu
    assert det2.units.short_label == "lbf, in"
    assert det2.element_results["B1"].bar_schedule.items[0].cut_length == old_cut_len


def test_f4_beam_result_to_core_without_dimensions_raises():
    """beam_result_to_core raises ValueError when section dimensions are missing."""
    from aci318.adapters.struct_core_adapter import beam_result_to_core
    beam_result = BeamDesignResult(
        required_flexure_As=2.0,
        suggested_bars="3 #8",
        provided_flexure_As=2.3,
        required_shear_spacing=12.0,
        stirrup_bar_size="#3",
        stirrup_legs=2,
    )
    with pytest.raises(ValueError, match="missing section dimensions"):
        beam_result_to_core(1, beam_result)
