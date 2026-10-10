"""
Tests for Biaxial Column Interaction (ACI 318-19 Section 10.5).
"""

import pytest
from aci318.codes.aci318_19 import ACI318_19
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.column import Column
from aci318.sections.circle import CircularSection
from aci318.sections.rectangle import RectangleSection, RebarLayer
from aci318.strength.interaction_strength import InteractionStrength


def _build_rect_column_section() -> RectangleSection:
    """Build a 16x20 in column with 4 #8 bars."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = RectangleSection(b=16.0, h=20.0, concrete=conc)
    # 2 #8 bars top (depth=2.5 in), 2 #8 bars bottom (depth=17.5 in)
    sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=2.5, steel=steel)
    sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=17.5, steel=steel)
    return sec


def _build_circle_column_section() -> CircularSection:
    """Build a 18 in diameter circular column with 6 #8 bars."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = CircularSection(D=18.0, concrete=conc)
    sec.setup_circular_bar_pattern(num_bars=6, bar_size="#8", cover=2.0, steel=steel)
    return sec


def test_uniaxial_column_interaction():
    sec = _build_rect_column_section()
    code = ACI318_19()
    checker = InteractionStrength(sec, code)

    # Pure uniaxial moment: Pu = 100 kip, Mu = 1200 kip-in (100 kip-ft)
    loads_uni = LoadEffects(Pu=100.0, Mu=1200.0)
    res_uni = checker.check(loads_uni)

    assert res_uni.status == "Passed"
    assert res_uni.demand_capacity_ratio > 0.0
    assert res_uni.phi_mn_x is not None
    assert "Uniaxial" in res_uni.method_used


def test_biaxial_rectangular_column_interaction():
    sec = _build_rect_column_section()
    code = ACI318_19()
    checker = InteractionStrength(sec, code)

    # 1. Major axis alone: Pu = 150 kip, Mu2 = 1000 kip-in, Mu3 = 0
    loads_x = LoadEffects(Pu=150.0, Mu2=1000.0, Mu3=0.0)
    res_x = checker.check(loads_x)

    # 2. Minor axis alone: Pu = 150 kip, Mu2 = 0, Mu3 = 600 kip-in
    loads_y = LoadEffects(Pu=150.0, Mu2=0.0, Mu3=600.0)
    res_y = checker.check(loads_y)

    # 3. Biaxial combined: Pu = 150 kip, Mu2 = 1000 kip-in, Mu3 = 600 kip-in
    loads_bi = LoadEffects(Pu=150.0, Mu2=1000.0, Mu3=600.0)
    res_bi = checker.check(loads_bi)

    # Combined DCR must be strictly greater than individual uniaxial DCRs
    assert res_bi.demand_capacity_ratio > res_x.demand_capacity_ratio
    assert res_bi.demand_capacity_ratio > res_y.demand_capacity_ratio
    assert res_bi.phi_mn_x is not None
    assert res_bi.phi_mn_y is not None
    assert "Bresler" in res_bi.method_used


def test_biaxial_circular_column_interaction():
    sec = _build_circle_column_section()
    code = ACI318_19()
    checker = InteractionStrength(sec, code)

    # Mux = 600 kip-in, Muy = 800 kip-in -> Resultant Mu = 1000 kip-in
    loads_bi = LoadEffects(Pu=100.0, Mu2=600.0, Mu3=800.0)
    res_bi = checker.check(loads_bi)

    loads_equiv = LoadEffects(Pu=100.0, Mu=1000.0)
    res_equiv = checker.check(loads_equiv)

    # Circular column DCR should match the resultant uniaxial moment
    assert res_bi.demand_capacity_ratio == pytest.approx(res_equiv.demand_capacity_ratio, rel=1e-3)
    assert "Circular" in res_bi.method_used


def test_column_member_design_with_biaxial():
    sec = _build_rect_column_section()
    code = ACI318_19()
    col = Column(section=sec, code=code, member_id="C101")

    loads = LoadEffects(Pu=200.0, Mu2=900.0, Mu3=500.0, Vu2=25.0, Vu3=15.0)
    result = col.design(loads)

    assert result.status in ("Passed", "Warning", "Failed")
    assert result.pm_interaction is not None
    assert result.pm_interaction.biaxial_ratio is not None
