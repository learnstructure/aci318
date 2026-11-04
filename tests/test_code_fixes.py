"""
Comprehensive tests verifying code compliance, safety fixes, and advanced foundations:
- Column axial overload detection (Pu > phi*Pn,max or Pu < phi*Pnt with Mu = 0)
- Beam high-shear auto-design stirrup spacing
- High-strength steel Grade 80 and 100 phi factors and development psi_g
- T-Beam flanged cracked transformed moment of inertia
- Soil bearing lift-off for eccentric spread footings (e > L/6)
- PileCap foundation designer
- RaftFoundation mat designer
"""

import math
import pytest

from aci318.codes.aci318_19 import ACI318_19
from aci318.codes.aci318_25 import ACI318_25
from aci318.foundations.isolated import IsolatedFooting
from aci318.foundations.pilecap import PileCap, PileCapDesignResult
from aci318.foundations.raft import RaftFoundation, RaftFoundationDesignResult
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.beam import Beam
from aci318.members.column import Column
from aci318.sections.rectangle import RectangleSection
from aci318.sections.tbeam import TBeamSection
from aci318.serviceability.deflection import calculate_cracked_inertia
from aci318.strength.development.development_length_engine import calculate_development_length
from aci318.strength.interaction_strength import InteractionStrength


def test_column_pure_axial_overload_fails():
    """Verify that an axially overloaded column fails immediately even if Mu = 0."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = RectangleSection(b=14.0, h=14.0, concrete=conc)
    sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=2.5, steel=steel)
    sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=11.5, steel=steel)

    code = ACI318_19()
    col = Column(section=sec, code=code)

    # phi*Pn,max for 14x14 column is ~ 450 - 550 kips
    # Test with Pu = 2000 kips, Mu = 0
    overload = LoadEffects(Pu=2000.0, Mu=0.0)
    res = col.check(overload)

    assert res.status == "Failed"
    assert res.pm_interaction.demand_capacity_ratio > 1.0
    assert any("exceeds maximum design axial capacity" in m for m in res.messages)


def test_column_tension_overload_fails():
    """Verify that an overloaded tension column fails immediately."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = RectangleSection(b=14.0, h=14.0, concrete=conc)
    # 4 #8 bars total = 4 * 0.79 = 3.16 in^2 -> phi*Pnt = 0.90 * 3.16 * 60 = 170.6 kips
    sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=2.5, steel=steel)
    sec.add_rebar_layer(num_bars=2, bar_size="#8", depth=11.5, steel=steel)

    code = ACI318_19()
    checker = InteractionStrength(sec, code)

    # Pu = -300 kips (tension overload)
    res = checker.check(LoadEffects(Pu=-300.0, Mu=0.0))
    assert res.status == "Failed"
    assert res.demand_capacity_ratio > 1.0
    assert any("exceeds design tension capacity" in m for m in res.messages)


def test_beam_high_shear_auto_design_passes():
    """Verify that a beam requiring tight stirrups (Vs > capacity at 12 in) is designed and passes."""
    conc = Concrete(fc=4.0)
    sec = RectangleSection(b=12.0, h=22.0, concrete=conc)
    code = ACI318_19()

    beam = Beam(section=sec, code=code, stirrup_bar_size="#3", stirrup_legs=2)
    # Vu = 42 kips, Mu = 1200 kip-in, d = 19.5 in
    # Designed stirrups satisfy Av,min, so Vc = 2 sqrt(f'c) bw d = 29.6 kips (Table 22.5.5.1(a)).
    # At s = 12 in: phi*Vn = 0.75 * (29.6 + 2 * 0.11 * 60 * 19.5 / 12) = 38.3 kips < 42 kips.
    # Vs,req = 42 / 0.75 - 29.6 = 26.4 kips -> s <= 0.22 * 60 * 19.5 / 26.4 = 9.75 in -> 9.5 in.
    loads = LoadEffects(Mu=1200.0, Vu=42.0)
    res = beam.design(loads)

    assert res.status in ("Passed", "Warning")
    assert res.status != "Failed"
    assert res.required_shear_spacing == 9.5
    assert res.shear.demand_capacity_ratio <= 1.0
    assert res.provided_flexure_As > 0.0


def test_high_strength_steel_phi_and_psi_g():
    """Verify ACI 318-19 and ACI 318-25 grade-dependent yield strain and psi_g factor."""
    code19 = ACI318_19()
    code25 = ACI318_25()

    # Grade 80: fy = 80 ksi -> eps_ty = 80 / 29000 = 0.002759
    # Transition zone: 0.002759 to 0.002759 + 0.003 = 0.005759
    strain_below_yield = 0.0025
    strain_in_transition = 0.0040
    strain_tension_controlled = 0.0060

    phi_comp = code19.get_phi_flexure(strain_below_yield, fy=80.0)
    assert phi_comp == pytest.approx(0.65, rel=1e-3)

    phi_trans = code19.get_phi_flexure(strain_in_transition, fy=80.0)
    assert 0.65 < phi_trans < 0.90

    phi_tens = code19.get_phi_flexure(strain_tension_controlled, fy=80.0)
    assert phi_tens == pytest.approx(0.90, rel=1e-3)

    # Table 25.4.2.5 Reinforcement grade factor psi_g
    assert code25.get_reinforcement_grade_factor(60.0) == 1.00
    assert code25.get_reinforcement_grade_factor(80.0) == 1.15
    assert code25.get_reinforcement_grade_factor(100.0) == 1.30

    conc = Concrete(fc=4.0)
    steel60 = Steel(fy=60.0)
    steel80 = Steel(fy=80.0)

    ld_60 = calculate_development_length(bar_diameter=1.0, steel=steel60, concrete=conc, code=code25)
    ld_80 = calculate_development_length(bar_diameter=1.0, steel=steel80, concrete=conc, code=code25)

    # Ratio should reflect fy ratio (80/60) times psi_g (1.15)
    expected_ratio = (80.0 / 60.0) * 1.15
    actual_ratio = ld_80.ld_tension / ld_60.ld_tension
    assert actual_ratio == pytest.approx(expected_ratio, rel=1e-2)


def test_tbeam_cracked_inertia_flange_contribution():
    """Verify that cracked moment of inertia for a T-beam accounts for flange width bf."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)

    # Rectangular section 12x24
    rect_sec = RectangleSection(b=12.0, h=24.0, concrete=conc)
    rect_sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)
    icr_rect = calculate_cracked_inertia(rect_sec)

    # T-beam with same web (bw=12, h=24) but flange bf=36, hf=5.0
    t_sec = TBeamSection(b_f=36.0, h_f=5.0, b_w=12.0, h=24.0, concrete=conc)
    t_sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)
    icr_tbeam = calculate_cracked_inertia(t_sec)

    # Flanged compression zone reduces neutral axis depth kd and increases Icr
    assert icr_tbeam > icr_rect


def test_footing_soil_bearing_lift_off():
    """Verify that when eccentricity e > L/6, triangular bearing pressure with lift-off is computed."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    ftg = IsolatedFooting(
        length=8.0, width=8.0, thickness=20.0,
        col_c1=18.0, col_c2=18.0,
        concrete=conc, steel=steel, code=code,
        allowable_q=6.0,
    )

    # L = 8 ft -> L/6 = 1.333 ft
    # Pu = 100 kips, Mu = 180 kip-ft = 2160 kip-in -> e = 1.80 ft > 1.333 ft (Lift-off occurs)
    loads_ecc = LoadEffects(Pu=100.0, Mu=2160.0)
    res = ftg.design(loads_ecc)

    # P/A + M/S would give: 100/64 + 180/(8*64/6) = 1.5625 + 2.109 = 3.67 ksf
    # Triangular bearing with lift-off: 2*P / (3*B*(L/2 - e)) = 200 / (3 * 8 * (4.0 - 1.8)) = 200 / (24 * 2.2) = 3.788 ksf
    assert res.max_bearing_pressure > 3.70
    assert res.max_bearing_pressure == pytest.approx(3.788, rel=2e-2)


def test_pile_cap_design():
    """Verify full design of a 4-pile reinforced concrete pile cap."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    pcap = PileCap(
        length=7.0, width=7.0, thickness=28.0,
        col_c1=18.0, col_c2=18.0,
        concrete=conc, steel=steel, code=code,
        num_piles=4, pile_capacity=150.0,
    )

    # Factored loads: Pu = 320 kips (80 kips per pile), Mu = 1200 kip-in (100 kip-ft)
    loads = LoadEffects(Pu=320.0, Mu=1200.0)
    res: PileCapDesignResult = pcap.design(loads)

    assert isinstance(res, PileCapDesignResult)
    assert res.status == "Passed"
    assert res.num_piles == 4
    assert res.max_pile_reaction > 80.0
    assert res.max_pile_reaction <= res.allowable_pile_capacity
    assert res.punching_shear_column.status == "Passed"
    assert res.punching_shear_pile.status == "Passed"
    assert res.one_way_shear_x.status == "Passed"
    assert res.required_As_x > 0.0
    assert res.required_As_y > 0.0


def test_raft_foundation_design():
    """Verify full design of a reinforced concrete mat / raft foundation."""
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    mat = RaftFoundation(
        length=40.0, width=40.0, thickness=32.0,
        concrete=conc, steel=steel, code=code,
        allowable_q=4.0, typical_span_ft=20.0,
    )

    # 4 bays (9 columns), total building factored load Pu = 2400 kips, Mu = 4800 kip-in
    loads = LoadEffects(Pu=2400.0, Mu=4800.0)
    res: RaftFoundationDesignResult = mat.design(loads, col_axial_kip=300.0)

    assert isinstance(res, RaftFoundationDesignResult)
    assert res.status == "Passed"
    assert res.max_bearing_pressure < res.allowable_bearing_capacity
    assert res.punching_shear.status == "Passed"
    assert res.one_way_shear.status == "Passed"
    assert res.required_As_bottom > 0.0
    assert res.required_As_top > 0.0



def test_aci318_19_hook_development_length():
    """F8: ACI 318-19 Eq. 25.4.3.1a for hooked bar development length."""
    code = ACI318_19()
    # #8 bar (db = 1.0 in), fc = 4.0 ksi, fy = 60.0 ksi
    # Unconfined, not in column core (psi_r = 1.6, psi_o = 1.25) -> ~29.9 in
    ldh_unconfined = code.get_hook_development_length(db=1.0, fy=60.0, fc=4.0, confined=False, in_column_core=False)
    assert ldh_unconfined == pytest.approx(29.9, rel=1e-2)

    # Confined, inside column core (psi_r = 1.0, psi_o = 1.0) -> ~14.95 in
    ldh_confined = code.get_hook_development_length(db=1.0, fy=60.0, fc=4.0, confined=True, in_column_core=True)
    assert ldh_confined == pytest.approx(14.95, rel=1e-2)


def test_aci318_19_one_way_shear_vc_no_artificial_lower_bound():
    """F9: Deep beam without stirrups follows Table 22.5.5.1(c) size effect without artificial 1.0*sqrt(fc) floor."""
    code = ACI318_19()
    # 12 x 44 in beam, d = 41 in, 2 #8 bars (As = 1.58 in^2), fc = 4.0 ksi, Av = 0
    bw = 12.0
    d = 41.0
    rho_w = 1.58 / (bw * d)
    vc = code.get_vc(f_c=4.0, b_w=bw, d=d, A_v=0.0, A_v_min=0.05, rho_w=rho_w)
    phi_vc = 0.75 * vc
    # Table 22.5.5.1(c): phi * Vc = 17.25 kip (with old 1.0*sqrt(fc) limit it was 23.34 kip)
    assert phi_vc == pytest.approx(17.25, rel=1e-2)
