"""
Tests for ACI 318-19 Serviceability (Deflections, Crack Control),
Foundation Engineers (Strip & Combined Footings), and Hook Development.
"""

import math
import pytest

from aci318.codes.aci318_19 import ACI318_19
from aci318.foundations.combined import CombinedFooting
from aci318.foundations.isolated import IsolatedFooting
from aci318.foundations.strip import StripFooting
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.serviceability.crack import check_crack_control_spacing, verify_crack_control
from aci318.serviceability.deflection import (
    calculate_beam_deflection,
    calculate_cracked_inertia,
    calculate_cracking_moment,
    calculate_effective_inertia,
    calculate_long_term_factor,
)
from aci318.strength.development.development_length_engine import calculate_development_length


def test_cracking_moment():
    conc = Concrete(fc=4.0)  # f'c = 4000 psi
    sec = RectangleSection(b=12.0, h=24.0, concrete=conc)
    # fr = 7.5 * sqrt(4000) = 474.34 psi = 0.4743 ksi
    # Ig = 12 * 24^3 / 12 = 13824 in^4
    # yt = 12 in
    # Mcr = 0.4743 * 13824 / 12 = 546.4 kip-in
    mcr = calculate_cracking_moment(sec)
    expected_mcr = (7.5 * math.sqrt(4000.0) / 1000.0) * (12.0 * (24.0 ** 3) / 12.0) / 12.0
    assert mcr == pytest.approx(expected_mcr, rel=1e-3)


def test_cracked_and_effective_inertia_bischoff():
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = RectangleSection(b=12.0, h=24.0, concrete=conc)
    # 3 #8 bars (As = 2.37 in^2) at d = 21.5 in
    sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)

    icr = calculate_cracked_inertia(sec)
    assert 2000.0 < icr < 5500.0
    assert icr < sec.gross_inertia

    mcr = calculate_cracking_moment(sec)

    # When Ma <= (2/3)*Mcr, Ie must strictly equal Ig
    ma_low = 0.5 * mcr
    ie_low = calculate_effective_inertia(sec, ma=ma_low, icr=icr)
    assert ie_low == pytest.approx(sec.gross_inertia, rel=1e-5)

    # When Ma > (2/3)*Mcr, Ie must be between Icr and Ig
    ma_high = 2.0 * mcr
    ie_high = calculate_effective_inertia(sec, ma=ma_high, icr=icr)
    assert icr <= ie_high <= sec.gross_inertia


def test_long_term_deflection_multiplier():
    # ACI 318-19 §24.2.4.1.1: 5-year sustained load factor with no compression steel = 2.0
    lambda_delta = calculate_long_term_factor(sustained_months=60.0, rho_prime=0.0)
    assert lambda_delta == pytest.approx(2.0, rel=1e-3)

    # Compression steel reduces creep deflection: 2.0 / (1 + 50 * 0.01) = 2.0 / 1.5 = 1.333
    lambda_delta_comp = calculate_long_term_factor(sustained_months=60.0, rho_prime=0.01)
    assert lambda_delta_comp == pytest.approx(2.0 / 1.5, rel=1e-3)


def test_beam_deflection_evaluation():
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = RectangleSection(b=12.0, h=24.0, concrete=conc)
    sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)

    # 20-ft span (240 inches), w_d = 1.0 klf = 1.0/12 kip/in, w_l = 0.8 klf = 0.8/12 kip/in
    res = calculate_beam_deflection(
        span_in=240.0,
        section=sec,
        w_dead_kip_per_in=1.0 / 12.0,
        w_live_kip_per_in=0.8 / 12.0,
        support_condition="simple",
    )
    assert res.immediate_dead_deflection > 0.0
    assert res.immediate_live_deflection > 0.0
    assert res.total_deflection > res.immediate_dead_deflection
    assert res.status in ("Passed", "Failed")


def test_crack_control_spacing():
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    sec = RectangleSection(b=12.0, h=24.0, concrete=conc)
    sec.add_rebar_layer(num_bars=3, bar_size="#8", depth=21.5, steel=steel)

    # fs = 2/3 * 60 = 40 ksi = 40,000 psi
    # s_max = min(15*(40000/40000) - 2.5*1.5, 12*(40000/40000)) = min(11.25, 12.0) = 11.25 in
    s_max = check_crack_control_spacing(sec, fs=40.0, cc=1.5)
    assert s_max == pytest.approx(11.25, rel=1e-3)

    chk_pass = verify_crack_control(sec, provided_spacing=8.0, fs=40.0, cc=1.5)
    assert chk_pass.passed

    chk_fail = verify_crack_control(sec, provided_spacing=14.0, fs=40.0, cc=1.5)
    assert not chk_fail.passed


def test_hook_development_lightweight_concrete():
    code = ACI318_19()
    steel = Steel(fy=60.0)
    # Normal weight concrete
    conc_nw = Concrete(fc=4.0)
    res_nw = calculate_development_length(bar_diameter=1.0, steel=steel, concrete=conc_nw, code=code)

    # Lightweight concrete (lambda = 0.75)
    conc_lw = Concrete(fc=4.0, concrete_type="all-lightweight")
    res_lw = calculate_development_length(bar_diameter=1.0, steel=steel, concrete=conc_lw, code=code)

    # Required hook length ldh in lightweight concrete must be GREATER than in normal-weight concrete
    assert res_lw.ldh_hook > res_nw.ldh_hook


def test_strip_footing_design():
    conc = Concrete(fc=3.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    strip = StripFooting(
        width=4.0,           # 4-ft wide footing
        thickness=14.0,      # 14 in thick
        wall_thickness=10.0, # 10 in wall
        concrete=conc,
        steel=steel,
        code=code,
        allowable_q=3.5,     # 3.5 ksf
    )

    loads = LoadEffects(Pu=8.0)  # 8 kips/ft wall load
    res = strip.design(loads)

    from aci318.results.footing import StripFootingDesignResult
    from aci318.detailing import StripFootingDetail
    assert isinstance(res, StripFootingDesignResult)
    assert isinstance(res.detailing, StripFootingDetail)
    assert res.status == "Passed"
    assert res.max_bearing_pressure <= 3.5
    assert res.transverse_bar_spacing > 0
    assert res.longitudinal_bar_count >= 2
    assert res.one_way_shear.status == "Passed"


def test_combined_footing_design():
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    comb = CombinedFooting(
        column_spacing_ft=14.0,
        col1_c1=18.0, col1_c2=18.0,
        col2_c1=20.0, col2_c2=20.0,
        concrete=conc,
        steel=steel,
        code=code,
        allowable_q=5.0,
        cantilever_col1_ft=2.0,
        thickness=28.0,
    )

    res = comb.design(p1_kip=200.0, p2_kip=300.0)

    from aci318.results.footing import CombinedFootingDesignResult
    from aci318.detailing import CombinedFootingDetail
    assert isinstance(res, CombinedFootingDesignResult)
    assert isinstance(res.detailing, CombinedFootingDetail)
    assert res.status in ("Passed", "Warning")
    assert res.length > 14.0
    assert res.width >= 3.0
    assert res.soil_pressure <= 5.0
    assert res.punching_shear_col1.status in ("Passed", "Warning")
    assert res.punching_shear_col2.status in ("Passed", "Warning")
    assert res.detailing is not None


def test_isolated_footing_punching_size_effect():
    conc = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    # Deep footing: 36 in thick (d ~ 32.5 in)
    # lambda_s = sqrt(2 / (1 + 32.5/10)) = 0.686
    ftg = IsolatedFooting(
        length=10.0, width=10.0, thickness=36.0,
        col_c1=24.0, col_c2=24.0,
        concrete=conc, steel=steel, code=code,
        allowable_q=6.0,
    )

    from aci318.foundations import IsolatedFootingDesignResult
    from aci318.results.footing import IsolatedFootingDesignResult as FootingResultFromResults
    from aci318.detailing import IsolatedFootingDetail

    res = ftg.design(LoadEffects(Pu=350.0))
    assert isinstance(res, IsolatedFootingDesignResult)
    assert isinstance(res, FootingResultFromResults)
    assert isinstance(res.detailing, IsolatedFootingDetail)
    assert res.punching_shear is not None
    assert res.punching_shear.phi_vn > 0.0
