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
    DesignResult,
    DetailingResult,
    ElasticMaterial,
    ElementDesignResult,
    ElementDetailingResult,
    ElementResult,
    FlexureDesignResult,
    Node,
    Project,
    RectangularSection,
    ShearDesignResult,
    StructuralModel,
)
from aci318.adapters import design_from_core
from aci318.results.beam import BeamDesignResult


def test_design_from_core_rejects_missing_results():
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)
    mat = ElasticMaterial(id="Conc", E=30000000.0, rho=2400.0)
    sec = RectangularSection(id="B12x18", b=12.0, h=18.0)
    elem = BeamElement(id=1, start_node=1, end_node=2, material_id="Conc", section_id="B12x18")

    model = StructuralModel(nodes=[node1, node2], materials=[mat], sections=[sec], elements=[elem])

    with pytest.raises(ValueError, match="No precomputed aci318 design/detailing result"):
        design_from_core(model)


def test_design_from_core_converts_existing_beam_results():
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)
    mat = ElasticMaterial(id="Conc", E=30000000.0, rho=2400.0)
    sec = RectangularSection(id="B12x18", b=12.0, h=18.0)
    elem = BeamElement(id=1, start_node=1, end_node=2, material_id="Conc", section_id="B12x18")
    model = StructuralModel(nodes=[node1, node2], materials=[mat], sections=[sec], elements=[elem])

    beam_result = BeamDesignResult(
        required_flexure_As=2.0,
        suggested_bars="3 #8",
        provided_flexure_As=2.3,
        required_shear_spacing=12.0,
        stirrup_bar_size="#3",
        stirrup_legs=2,
        status="Passed",
        messages=["beam design ok"],
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
    sf = BeamSectionForce(station=0.0, P=100.0, Vy=8.0, Mz=120.0)
    ar = AnalysisResult(analysis_case_id="A1", element_results={1: ElementResult(element_id=1, forces=[sf])})

    loads = __import__("aci318.adapters.struct_core_adapter", fromlist=["analysis_result_to_load_effects"]).analysis_result_to_load_effects(1, ar)

    assert loads is not None
    assert loads.Pu == 100.0
    assert loads.Vu == 8.0
    assert loads.Mu == 120.0


def test_design_from_core_with_project_units():
    from struct_core import Metadata, Units
    node1 = Node(id=1, x=0.0, y=0.0)
    node2 = Node(id=2, x=6.0, y=0.0)  # 6.0 meters
    mat = ElasticMaterial(id="Conc", E=30000000.0, rho=2400.0)
    sec = RectangularSection(id="B300x500", b=0.30, h=0.50)  # 0.30m x 0.50m
    elem = BeamElement(id=1, start_node=1, end_node=2, material_id="Conc", section_id="B300x500")
    model = StructuralModel(nodes=[node1, node2], materials=[mat], sections=[sec], elements=[elem])

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
    # 100 kN * 0.22480894 = 22.48 kips
    assert pytest.approx(loads.Pu, rel=1e-3) == 22.481
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
    mat = ElasticMaterial(id="Conc", E=30000000.0, rho=2400.0)
    sec = RectangularSection(id="B300x500", b=0.30, h=0.50)  # 0.30m x 0.50m
    elem = BeamElement(id=1, start_node=1, end_node=2, material_id="Conc", section_id="B300x500")
    model = StructuralModel(nodes=[node1, node2], materials=[mat], sections=[sec], elements=[elem])

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



