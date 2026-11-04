"""Longitudinal reinforcement design of columns (aci318.members.column_reinforcement)."""

import pytest

from aci318.codes.aci318_25 import ACI318_25
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.column import Column
from aci318.members.column_reinforcement import (
    MAX_RATIO,
    MAX_RATIO_SPECIAL_FRAME,
    apply_layout,
    candidate_layouts,
    design_longitudinal_reinforcement,
    max_longitudinal_ratio,
)
from aci318.sections.circle import CircularSection
from aci318.sections.rectangle import RectangleSection

CODE = ACI318_25()
CONC = Concrete(fc=4.0)
STEEL = Steel(fy=60.0)


def _dcr(section, layout, loads):
    apply_layout(section, layout, STEEL)
    return Column(section=section, code=CODE).design(loads).axial_flexure.demand_capacity_ratio


def test_steel_limits_of_the_frame_system():
    assert max_longitudinal_ratio("smf") == MAX_RATIO_SPECIAL_FRAME == 0.06  # §18.7.4.1
    for system in ("imf", "omf", "none"):
        assert max_longitudinal_ratio(system) == MAX_RATIO == 0.08  # §10.6.1.1


def test_lightly_loaded_column_keeps_the_minimum_ratio():
    sec = RectangleSection(b=20.0, h=20.0, concrete=CONC)
    design = design_longitudinal_reinforcement(sec, [LoadEffects(Pu=300.0, Mu2=1000.0)], CODE, STEEL, 0.06)
    assert design.adequate and design.layout == candidate_layouts(sec, 0.06)[0]
    assert design.result.axial_flexure.required_steel == pytest.approx(design.layout.area)


@pytest.mark.parametrize("make_section, loads", [
    (lambda: RectangleSection(b=20.0, h=20.0, concrete=CONC), [LoadEffects(Pu=600.0, Mu2=5000.0)]),
    (lambda: RectangleSection(b=16.0, h=24.0, concrete=CONC),
     [LoadEffects(Pu=300.0, Mu2=6000.0), LoadEffects(Pu=50.0, Mu2=4000.0, Mu3=1500.0)]),
    (lambda: CircularSection(D=20.0, concrete=CONC), [LoadEffects(Pu=550.0, Mu2=3500.0)]),
])
def test_design_is_the_lightest_adequate_layout(make_section, loads):
    """The search equals an exhaustive check of every candidate (strength need not grow with the
    area across bar sizes, so a bisection over all candidates could miss the lightest)."""
    section = make_section()
    design = design_longitudinal_reinforcement(section, loads, CODE, STEEL, 0.08)
    reference = make_section()
    lightest = next(lay for lay in candidate_layouts(reference, 0.08) if _dcr(reference, lay, loads) <= 1.0)
    assert design.adequate and design.layout == lightest
    assert design.layout.area > 0.01 * section.gross_area * 1.2  # the minimum was not enough
    # the designed bars are the ones left on the section
    assert sum(lyr.area for lyr in section.layers) == pytest.approx(design.layout.area)


def test_overloaded_column_reports_the_steel_limit():
    sec = RectangleSection(b=20.0, h=20.0, concrete=CONC)
    design = design_longitudinal_reinforcement(sec, [LoadEffects(Pu=2000.0, Mu2=20000.0)], CODE, STEEL, 0.06)
    assert not design.adequate and design.layout == candidate_layouts(sec, 0.06)[-1]
    assert design.result.axial_flexure.demand_capacity_ratio > 1.0
    assert any("6% limit" in m for m in design.result.messages)


def test_layouts_respect_clear_spacing_and_a_too_small_section_is_refused():
    sec = RectangleSection(b=12.0, h=12.0, concrete=CONC)
    for layout in candidate_layouts(sec, 0.08):
        apply_layout(sec, layout, STEEL)
        n_b, n_h = sec.bar_pattern[:2]
        assert layout.area <= 0.08 * sec.gross_area + 1e-9 and min(n_b, n_h) >= 2
    with pytest.raises(ValueError, match="clear spacing"):
        candidate_layouts(RectangleSection(b=5.5, h=5.5, concrete=CONC), 0.08)


def test_hx_limit_of_highly_loaded_special_frame_columns_is_designed_for():
    """§18.7.5.2(f): 8 in where Pu > 0.3 Ag f'c (or f'c > 10 ksi) in SMF columns, else 14 in."""
    from aci318.members.column_reinforcement import max_supported_bar_spacing, perimeter_bar_spacing

    ag, fc = 24.0 * 24.0, 4.0
    assert max_supported_bar_spacing("smf", 0.31 * ag * fc, ag, fc) == 8.0
    assert max_supported_bar_spacing("smf", 0.29 * ag * fc, ag, fc) == 14.0
    assert max_supported_bar_spacing("smf", 0.0, ag, 12.0) == 8.0
    assert max_supported_bar_spacing("imf", 0.5 * ag * fc, ag, fc) == 14.0
    sec = RectangleSection(b=24.0, h=24.0, concrete=CONC)
    layouts = candidate_layouts(sec, 0.06, max_spacing=8.0)
    assert layouts and layouts[0].num_bars > candidate_layouts(sec, 0.06)[0].num_bars
    for layout in layouts:
        apply_layout(sec, layout, STEEL)
        assert perimeter_bar_spacing(sec.b, sec.h, sec.bar_pattern[:2], layout.bar_size) <= 8.0
