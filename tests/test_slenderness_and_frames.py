"""
Regression tests for ACI 318-25 slenderness (Section 6.6.4) and moment-frame provisions
(Chapters 15 and 18).
"""

import math

import pytest

from aci318.codes.aci318_25 import ACI318_25
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.seismic import (
    FrameBeam, FrameColumn, FrameJoint, beam_moment_strength, check_beam, check_column, check_joint,
)
from aci318.strength import slenderness as sl


# -----------------------------------------------------------------------------
# Section 6.6.4
# -----------------------------------------------------------------------------
def test_stability_index_and_sway_magnifier():
    q = sl.stability_index(sum_pu=2000.0, delta_o=0.5, v_us=100.0, l_c=144.0)
    assert q == pytest.approx(2000.0 * 0.5 / (100.0 * 144.0))
    assert sl.sway_magnifier(q) == pytest.approx(1.0 / (1.0 - q))
    assert sl.sway_magnifier(1.2) == math.inf


def test_equivalent_moment_factor_sign_convention():
    # single curvature, equal end moments (same internal-moment sign): Cm = 0.6 + 0.4 = 1.0
    assert sl.equivalent_moment_factor(100.0, 100.0) == pytest.approx(1.0)
    # double curvature, equal end moments: M1/M2 = +1 -> Cm = 0.2
    assert sl.equivalent_moment_factor(100.0, -100.0) == pytest.approx(0.2)
    # one end free of moment: Cm = 0.6
    assert sl.equivalent_moment_factor(0.0, 50.0) == pytest.approx(0.6)


def test_member_magnifier_and_minimum_moment():
    ei = sl.effective_stiffness(ec=3605.0, ig=16 ** 4 / 12.0, beta_dns=0.6)
    pc = sl.critical_buckling_load(ei, k=1.0, l_u=144.0)
    assert pc == pytest.approx(math.pi ** 2 * 0.4 * 3605.0 * 16 ** 4 / 12.0 / 1.6 / 144.0 ** 2)
    assert sl.member_magnifier(cm=1.0, pu=0.3 * pc, pc=pc) == pytest.approx(1.0 / (1.0 - 0.4))
    assert sl.member_magnifier(cm=0.4, pu=0.1 * pc, pc=pc) == 1.0          # >= 1.0
    assert sl.member_magnifier(cm=1.0, pu=0.8 * pc, pc=pc) == math.inf     # Pu >= 0.75 Pc
    assert sl.minimum_eccentricity(16.0) == pytest.approx(0.6 + 0.48)


# -----------------------------------------------------------------------------
# Chapters 15 and 18
# -----------------------------------------------------------------------------
CONC = Concrete(fc=4.0)


def _beam(bid="B1", n=3, size="#8", direction="x", b=14.0, h=24.0, span=216.0):
    return FrameBeam(id=bid, b=b, h=h, d=h - 2.5, clear_span=span, n_bars=n, bar_size=size,
                     concrete=CONC, wu=0.25, direction=direction)


def _column(cid, size=20.0, n_bars=8, bar="#9", pu=(150.0, 450.0)):
    sec = RectangleSection(b=size, h=size, concrete=CONC)
    sec.setup_perimeter_bar_pattern(n_bars, bar, steel=Steel(fy=60.0))
    n_b, n_h = sec.bar_pattern[:2]
    return FrameColumn(id=cid, section=sec, clear_height=120.0, pu_values=list(pu), vu_analysis=10.0,
                       bars_per_face=(n_b, n_h), bar_size=bar)


def test_smf_beam_capacity_shear_uses_probable_moments():
    code = ACI318_25()
    beam = _beam()
    checks = {c.clause: c for c in check_beam(beam, code, "smf", sds=1.0)}
    mpr = beam_moment_strength(beam, code, 1.25)
    ve = 2.0 * mpr / beam.clear_span + beam.wu * beam.clear_span / 2.0
    assert checks["ACI 318-25 §18.6.5"].demand == pytest.approx(ve)
    assert mpr == pytest.approx(1.25 * beam_moment_strength(beam, code, 1.0), rel=0.05)
    assert checks["ACI 318-25 §18.6.2.1(b)"].capacity == beam.b
    # A beam wider than allowed by rho <= 0.025 fails 18.6.3.1
    heavy = _beam(n=6, size="#11", b=12.0, h=20.0)
    rho = {c.clause: c for c in check_beam(heavy, code, "smf", sds=1.0)}["ACI 318-25 §18.6.3.1"]
    assert not rho.passed


def test_strong_column_weak_beam_and_joint_shear():
    code = ACI318_25()
    beams = {"BL": _beam("BL"), "BR": _beam("BR")}
    columns = {"C1": _column("C1"), "C2": _column("C2")}
    joint = FrameJoint(id="J", beams={"x": ["BL", "BR"]}, column_below="C1", column_above="C2",
                       height_below=144.0, height_above=144.0)
    checks = {c.clause: c for c in check_joint(joint, beams, columns, code, "smf")}
    scwb = checks["ACI 318-25 §18.7.3.2"]
    assert scwb.demand == pytest.approx(1.2 * 2 * beam_moment_strength(beams["BL"], code, 1.0))
    shear = checks["ACI 318-25 §18.8.4"]
    tension = 2 * 1.25 * 60.0 * 3 * 0.79
    assert shear.demand == pytest.approx(tension - 2 * beam_moment_strength(beams["BL"], code, 1.25) / 144.0)
    # continuous column and beams, not confined (no transverse beams): 15 sqrt(f'c) Aj, phi = 0.85
    assert shear.capacity == pytest.approx(0.85 * 15.0 * math.sqrt(4000.0) * 20.0 * 20.0 / 1000.0)

    # Weak columns fail strong-column/weak-beam
    weak = {"C1": _column("C1", size=14.0, n_bars=4, bar="#6"), "C2": _column("C2", size=14.0, n_bars=4, bar="#6")}
    scwb_weak = {c.clause: c for c in check_joint(joint, beams, weak, code, "smf")}["ACI 318-25 §18.7.3.2"]
    assert not scwb_weak.passed


def test_columns_are_proportioned_for_strong_column_weak_beam():
    """Column bars are raised (within 6 % Ag, 18.7.4.1) until sum(Mnc) >= 1.2 sum(Mnb); where steel cannot
    reach it, the columns end at the limit and the joint check reports the shortfall."""
    from aci318.members.column_reinforcement import candidate_layouts
    from aci318.seismic import proportion_for_strong_column, strong_column_demand

    code = ACI318_25()
    joint = FrameJoint(id="J", beams={"x": ["BL", "BR"]}, column_below="C1", column_above="C2",
                       height_below=144.0, height_above=144.0)

    def weak_columns():
        return {c: _column(c, size=16.0, n_bars=4, bar="#6") for c in ("C1", "C2")}

    beams = {"BL": _beam("BL"), "BR": _beam("BR")}
    columns = weak_columns()
    layouts = {c: candidate_layouts(col.section, 0.06) for c, col in columns.items()}
    demand, capacity = strong_column_demand(joint, "x", beams, columns, code)
    assert capacity < demand
    raised = proportion_for_strong_column([joint], beams, columns, code, layouts, Steel(fy=60.0))
    assert set(raised) == {"C1", "C2"} and all(lay.area <= 0.06 * 256.0 for lay in raised.values())
    demand, capacity = strong_column_demand(joint, "x", beams, columns, code)
    assert capacity >= demand
    scwb = {c.clause: c for c in check_joint(joint, beams, columns, code, "smf")}["ACI 318-25 §18.7.3.2"]
    assert scwb.passed

    # Beams too strong for any column steel within 6 % Ag
    strong = {"BL": _beam("BL", n=8, size="#11", h=36.0), "BR": _beam("BR", n=8, size="#11", h=36.0)}
    columns = weak_columns()
    raised = proportion_for_strong_column([joint], strong, columns, code, layouts, Steel(fy=60.0))
    assert all(raised[c] == layouts[c][-1] for c in ("C1", "C2"))
    demand, capacity = strong_column_demand(joint, "x", strong, columns, code)
    assert capacity < demand


def test_gravity_frame_joint_uses_chapter_15():
    code = ACI318_25()
    beams = {"BL": _beam("BL")}
    columns = {"C1": _column("C1")}
    joint = FrameJoint(id="J", beams={"x": ["BL"]}, column_below="C1", column_above=None,
                       height_below=144.0)
    checks = check_joint(joint, beams, columns, code, "none")
    assert [c.clause for c in checks] == ["ACI 318-25 §15.5"]
    # discontinuous column, single beam, not confined: 12 sqrt(f'c) Aj (Table 15.5.2.1), phi = 0.75
    assert checks[0].capacity == pytest.approx(0.75 * 12.0 * math.sqrt(4000.0) * 20.0 * 20.0 / 1000.0)


def test_continuous_gravity_joint_uses_analysis_moments():
    """15.4.2.1(a): balanced gravity moments transfer no joint shear; unbalanced ones do."""
    code = ACI318_25()
    columns = {"C1": _column("C1"), "C2": _column("C2")}
    joint = FrameJoint(id="J", beams={"x": ["BL", "BR"]}, column_below="C1", column_above="C2",
                       height_below=144.0, height_above=144.0)
    beams = {"BL": _beam("BL"), "BR": _beam("BR")}
    # Hogging at both faces: the beams apply equal and opposite moments to the joint
    beams["BL"].end_moments = {"J": {"G": 1500.0, "W": 1200.0}}
    beams["BR"].end_moments = {"J": {"G": -1500.0, "W": 600.0}}
    shear = check_joint(joint, beams, columns, code, "none")[0]
    assert shear.clause == "ACI 318-25 §15.5"
    jd = beam_moment_strength(beams["BL"], code, 1.0) / (60.0 * 3 * 0.79)
    # Combination W governs: both beams turn the joint the same way
    assert shear.demand == pytest.approx(1800.0 / jd - 1800.0 / 144.0)
    assert "15.4.2.1(a)" in shear.messages[0]
    # Without analysis moments the nominal strengths are used (15.4.2.1(b))
    nominal = check_joint(joint, {"BL": _beam("BL"), "BR": _beam("BR")}, columns, code, "none")[0]
    assert nominal.demand > shear.demand


def test_smf_column_checks_confinement_and_capacity_shear():
    code = ACI318_25()
    checks = {c.clause: c for c in check_column(_column("C1"), code, "smf", (5000.0, None))}
    assert {"ACI 318-25 §18.7.2.1(a)", "ACI 318-25 §18.7.5.4", "ACI 318-25 §18.7.6.1"} <= set(checks)
    shear = checks["ACI 318-25 §18.7.6.1"]
    assert shear.demand >= 10.0  # never below the analysis shear
    # too small a column for SMF
    small = {c.clause: c for c in check_column(_column("C2", size=10.0, n_bars=4, bar="#6"), code, "smf")}
    assert not small["ACI 318-25 §18.7.2.1(a)"].passed


@pytest.mark.parametrize("size_in", [11.8, 15.7, 19.7, 21.7, 23.6, 31.5, 47.2])
def test_column_layouts_meet_the_steel_limits_and_hx(size_in):
    """Candidate column bars: 1 %-6 % Ag, ordered by steel area, and supported-bar spacing <= 14 in
    (18.7.5.2(e)) as the seismic check measures it."""
    from aci318.members.column_reinforcement import apply_layout, candidate_layouts
    from aci318.seismic.moment_frames import FrameColumn, _hx

    sec = RectangleSection(b=size_in, h=size_in, concrete=CONC)
    layouts = candidate_layouts(sec, max_ratio=0.06)
    assert [lay.area for lay in layouts] == sorted(lay.area for lay in layouts)
    for layout in (layouts[0], layouts[-1]):
        assert 0.01 * sec.gross_area - 1e-9 <= layout.area <= 0.06 * sec.gross_area + 1e-9
        apply_layout(sec, layout, Steel(fy=60.0))
        col = FrameColumn(id="C", section=sec, clear_height=120.0, pu_values=[100.0], vu_analysis=1.0,
                          bars_per_face=sec.bar_pattern[:2], bar_size=layout.bar_size)
        assert _hx(col) <= 14.0
