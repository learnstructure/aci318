"""
Regression tests for ACI 318-25 provisions corrected in a code-compliance audit of the package
(the remaining gaps are listed in research_paper/benchmarks/code_compliance_notes.md).
"""

import pytest

from aci318.codes.aci318_19 import ACI318_19
from aci318.codes.aci318_25 import ACI318_25
from aci318.database.bars import Rebar
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.beam import Beam
from aci318.members.column import Column
from aci318.sections.rectangle import RectangleSection
from aci318.strength.interaction_strength import InteractionStrength


def test_lambda_from_equilibrium_density_table_19_2_4_1a():
    code = ACI318_25()
    assert code.get_lambda_(Concrete(fc=4.0, concrete_type="lightweight", density=95.0)) == 0.75
    assert code.get_lambda_(Concrete(fc=4.0, concrete_type="lightweight", density=120.0)) == pytest.approx(0.90)
    assert code.get_lambda_(Concrete(fc=4.0, concrete_type="lightweight", density=140.0)) == 1.0
    assert code.get_lambda_(Concrete(fc=4.0, concrete_type="sand-lightweight")) == 0.85
    assert code.get_lambda_(Concrete(fc=4.0, concrete_type="all-lightweight")) == 0.75
    # Normalweight concrete is 1.0 regardless of the stored density (§19.2.4.3)
    assert code.get_lambda_(Concrete(fc=4.0, density=120.0)) == 1.0
    with pytest.raises(ValueError):
        code.get_lambda_(Concrete(fc=4.0, concrete_type="foamed"))


def test_phi_cap_21_2_2_3_between_01fcag_and_pn_bal():
    """ACI 318-25 caps phi between 0.9 at 0.1 f'c Ag and phi_cc at Pn,bal; ACI 318-19 does not."""
    pn_low, pn_bal = 100.0, 500.0
    strain_t = 0.006  # tension-controlled by strain alone
    assert ACI318_19().get_phi_axial_flexure(strain_t, 300.0, pn_low, pn_bal) == 0.90
    capped = ACI318_25().get_phi_axial_flexure(strain_t, 300.0, pn_low, pn_bal)
    assert capped == pytest.approx(0.90 - 0.25 * (300.0 - 100.0) / 400.0)  # 0.775
    # Outside the range the strain-based phi applies
    assert ACI318_25().get_phi_axial_flexure(strain_t, 50.0, pn_low, pn_bal) == 0.90


def test_318_25_pm_diagram_is_not_stronger_than_318_19():
    conc = Concrete(fc=4.0)
    sec = RectangleSection(b=16.0, h=16.0, concrete=conc)
    sec.setup_perimeter_bar_pattern(8, "#7", steel=Steel(fy=60.0))
    loads = LoadEffects(Pu=200.0, Mu=1200.0)
    r19 = InteractionStrength(sec, ACI318_19()).check(loads)
    r25 = InteractionStrength(sec, ACI318_25()).check(loads)
    assert r25.phi_mn_x <= r19.phi_mn_x + 1e-9
    assert r25.demand_capacity_ratio >= r19.demand_capacity_ratio - 1e-9


def test_perimeter_bar_pattern_is_symmetric_and_rotates_for_weak_axis():
    conc = Concrete(fc=4.0)
    sec = RectangleSection(b=12.0, h=20.0, concrete=conc)
    sec.setup_perimeter_bar_pattern(10, "#7", steel=Steel(fy=60.0))
    assert sum(lyr.num_bars for lyr in sec.layers) == 10
    depths = [lyr.depth for lyr in sec.layers]
    assert depths == sorted(depths)
    # symmetric about mid-depth: equal steel above and below the centroid
    top = sum(l.area for l in sec.layers if l.depth < sec.h / 2)
    bottom = sum(l.area for l in sec.layers if l.depth > sec.h / 2)
    assert top == pytest.approx(bottom)

    weak = sec.get_weak_axis_section()
    assert (weak.b, weak.h) == (20.0, 12.0)
    assert sum(lyr.num_bars for lyr in weak.layers) == 10
    # bars per b-face of the weak section = bars per h-face of the strong section
    assert weak.layers[0].num_bars == len(sec.layers)


def test_column_checks_tension_with_its_own_moment():
    """A column under uplift and bending is weaker than under compression with the same moment."""
    conc = Concrete(fc=4.0)
    sec = RectangleSection(b=14.0, h=14.0, concrete=conc)
    sec.setup_perimeter_bar_pattern(4, "#7", steel=Steel(fy=60.0))
    col = Column(section=sec, code=ACI318_25())
    gravity = LoadEffects(Pu=150.0, Mu=600.0)
    uplift = LoadEffects(Pu=-40.0, Mu=600.0)
    both = col.design([gravity, uplift]).pm_interaction.demand_capacity_ratio
    assert both == pytest.approx(col.design(uplift).pm_interaction.demand_capacity_ratio)
    assert both > col.design(gravity).pm_interaction.demand_capacity_ratio


def test_beam_design_is_tension_controlled_9_3_3_1():
    """A layout that is strong enough but not tension-controlled is rejected."""
    from aci318.strength.flexure_strength import FlexureStrength

    code = ACI318_25()
    eps_tc = code.get_tension_controlled_strain(60.0)
    sec = RectangleSection(b=12.0, h=18.0, concrete=Concrete(fc=4.0))

    # 5 #8 resists Mu = 2300 kip-in by strength, but in the transition zone (eps_t ~ 0.0038)
    trial = RectangleSection(b=12.0, h=18.0, concrete=Concrete(fc=4.0))
    trial.add_rebar_layer(num_bars=5, bar_size="#8", depth=15.5, steel=Steel(fy=60.0))
    strength_only = FlexureStrength(trial, code).check(LoadEffects(Mu=2300.0))
    assert strength_only.demand_capacity_ratio <= 1.0
    assert strength_only.steel_strain < eps_tc

    res = Beam(section=sec, code=code).design(LoadEffects(Mu=2300.0, Vu=10.0))
    assert res.status == "Failed"
    assert res.suggested_bars == "None"

    # Moderate moment: designed, tension-controlled
    ok = Beam(section=sec, code=code).design(LoadEffects(Mu=1800.0, Vu=10.0))
    assert ok.status != "Failed"
    assert ok.flexure.steel_strain >= eps_tc
    assert ok.ductility_ratio <= 1.0


def test_beam_stirrups_carry_shear_plus_torsion():
    """Each outer stirrup leg must provide Av/(n s) + At/s (ACI 318 §9.5.4, §22.7.6.1)."""
    code = ACI318_25()
    sec = RectangleSection(b=14.0, h=24.0, concrete=Concrete(fc=4.0))
    loads = LoadEffects(Mu=900.0, Vu=30.0, Tu=150.0)
    res = Beam(section=sec, code=code).design(loads)
    assert res.torsion is not None
    assert res.torsion.demand_capacity_ratio <= 1.0
    assert res.torsion.required_longitudinal_steel > 0.0

    # Same shear without torsion needs no tighter stirrups
    no_t = Beam(section=sec, code=code).design(LoadEffects(Mu=900.0, Vu=30.0))
    leg = Rebar(bar_size=res.stirrup_bar_size).area
    leg_nt = Rebar(bar_size=no_t.stirrup_bar_size).area
    assert leg / res.required_shear_spacing > leg_nt / no_t.required_shear_spacing


def test_footing_punching_includes_moment_transfer():
    """ACI 318-25 §8.4.4.2.3: the unbalanced column moment adds gamma_v Msc c / Jc to the punching stress."""
    from aci318.foundations.isolated import IsolatedFooting

    def punching(mu):
        ftg = IsolatedFooting(length=8.0, width=8.0, thickness=20.0, col_c1=18.0, col_c2=18.0,
                              concrete=Concrete(fc=4.0), steel=Steel(fy=60.0), code=ACI318_25())
        return ftg.design(LoadEffects(Pu=300.0, Mu=mu)).punching_shear.demand_capacity_ratio

    base, with_moment = punching(0.0), punching(1200.0)
    d = 20.0 - 3.0 - 0.75
    b1 = 18.0 + d
    gamma_v = 1.0 - 1.0 / (1.0 + 2.0 / 3.0)
    jc = d * b1 ** 3 / 6.0 + b1 * d ** 3 / 6.0 + d * b1 * b1 ** 2 / 2.0
    added = gamma_v * 1200.0 * (b1 / 2.0) / jc
    vc = 4.0 * min((2.0 / (1.0 + d / 10.0)) ** 0.5, 1.0) * (4000.0 ** 0.5) / 1000.0
    assert with_moment - base == pytest.approx(added / (0.75 * vc), rel=1e-6)


def test_fy_limits_table_20_2_2_4():
    code = ACI318_25()
    # As,min uses fy <= 80 ksi (§9.6.1.2)
    assert code.get_minimum_steel_ratio(4.0, 100.0) == code.get_minimum_steel_ratio(4.0, 80.0)
    # Shear reinforcement fyt <= 60 ksi
    from aci318.strength.shear_strength import ShearStrength

    sec = RectangleSection(b=12.0, h=20.0, concrete=Concrete(fc=4.0))
    assert ShearStrength(sec, code, fy_shear=80.0).fy_shear == 60.0
