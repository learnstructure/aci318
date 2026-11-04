"""
Longitudinal reinforcement design of tied columns (ACI 318-25).

A column's longitudinal bars are chosen for strength: the lightest layout of equal bars, between
the minimum ratio of §10.6.1.1 (0.01 Ag) and the maximum of the frame system (§10.6.1.1: 0.08 Ag;
§18.7.4.1, special moment frames: 0.06 Ag), whose axial and axial-flexural (P-M) strength carries
every load set. In special moment frames, ``aci318.seismic.strong_column`` then raises the bars of
columns at joints failing strong-column/weak-beam (§18.7.3.2). The other column checks (shear, and the
Chapter 18 checks of the frame) are made with the designed bars.

Candidate layouts:

* rectangular sections: equal bars spread over the perimeter (``RectangleSection.perimeter_bar_counts``),
  with every face's center-to-center spacing within the hx limit (``max_supported_bar_spacing``), so that
  with every bar tied the spacing of laterally supported bars meets §18.7.5.2(e)/(f);
* circular sections: at least six equal bars on a circle;
* both: clear spacing between bars at least max(1.5 in, 1.5 db) (§25.2.3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union

from aci318.codes.base import DesignCode
from aci318.database.bars import BAR_DATABASE
from aci318.loads.load_effects import LoadEffects
from aci318.materials.steel import Steel
from aci318.members.column import Column
from aci318.results.column import ColumnDesignResult
from aci318.sections.circle import CircularSection
from aci318.sections.rectangle import DEFAULT_COVER, RectangleSection

Section = Union[RectangleSection, CircularSection]

COLUMN_BAR_SIZES = ("#6", "#7", "#8", "#9", "#10", "#11")
MIN_RATIO = 0.01                 # ACI 318-25 §10.6.1.1
MAX_RATIO = 0.08                 # ACI 318-25 §10.6.1.1
MAX_RATIO_SPECIAL_FRAME = 0.06   # ACI 318-25 §18.7.4.1
HOOP_DIAMETER = 0.5              # in, transverse bar assumed in bar-position geometry (#4)
MAX_SUPPORTED_SPACING = 14.0     # in, center to center (§18.7.5.2(e))
MAX_SUPPORTED_SPACING_HIGH_AXIAL = 8.0  # in (§18.7.5.2(f))
MIN_CIRCULAR_BARS = 6


@dataclass(frozen=True)
class LongitudinalLayout:
    """Equal longitudinal bars of one size."""

    num_bars: int
    bar_size: str

    @property
    def area(self) -> float:
        """Total bar area (in^2)."""
        return self.num_bars * BAR_DATABASE[self.bar_size]["area"]

    @property
    def weight_order(self) -> Tuple[float, int]:
        """Ordering from lightest: steel area, then number of bars."""
        return self.area, self.num_bars

    def __str__(self) -> str:
        return f"{self.num_bars} {self.bar_size}"


@dataclass
class ColumnReinforcementDesign:
    """Designed layout, the column check made with it, and whether strength was reached within the limits."""

    layout: LongitudinalLayout
    result: ColumnDesignResult
    adequate: bool


def max_longitudinal_ratio(frame_system: str) -> float:
    """Largest Ast / Ag: 0.06 for special moment frames (§18.7.4.1), otherwise 0.08 (§10.6.1.1)."""
    return MAX_RATIO_SPECIAL_FRAME if frame_system == "smf" else MAX_RATIO


def max_supported_bar_spacing(frame_system: str, pu_max: float, ag: float, fc: float) -> float:
    """
    Limit on the spacing hx of laterally supported column bars (in): 8 in in special moment frames where
    Pu > 0.3 Ag f'c or f'c > 10 ksi (§18.7.5.2(f)), otherwise 14 in (§18.7.5.2(e)), which the layouts of
    every frame keep. ``pu_max`` in kip, ``ag`` in in^2, ``fc`` in ksi.
    """
    if frame_system == "smf" and (pu_max > 0.3 * ag * fc or fc > 10.0):
        return MAX_SUPPORTED_SPACING_HIGH_AXIAL
    return MAX_SUPPORTED_SPACING


def perimeter_bar_spacing(
    b: float, h: float, bars_per_face: Sequence[int], bar_size: str, cover: float = DEFAULT_COVER
) -> float:
    """Largest center-to-center bar spacing on the faces of a rectangular perimeter layout (in), with clear
    ``cover`` to the transverse reinforcement."""
    n_b, n_h = bars_per_face
    edge = cover + HOOP_DIAMETER + BAR_DATABASE[bar_size]["diameter"] / 2.0
    return max((b - 2.0 * edge) / max(n_b - 1, 1), (h - 2.0 * edge) / max(n_h - 1, 1))


def _min_clear_spacing(bar_size: str) -> float:
    """§25.2.3: clear spacing of column bars at least 1.5 in and 1.5 db."""
    return max(1.5, 1.5 * BAR_DATABASE[bar_size]["diameter"])


def _bar_spacings(section: Section, layout: LongitudinalLayout) -> Optional[Tuple[float, float]]:
    """(least clear spacing, largest center-to-center spacing) of ``layout`` in ``section`` (in), or None
    when the bars do not fit inside the cover and transverse reinforcement."""
    db = BAR_DATABASE[layout.bar_size]["diameter"]
    if isinstance(section, CircularSection):
        radius = section.D / 2.0 - section.cover - HOOP_DIAMETER - db / 2.0
        if radius <= 0.0:
            return None
        pitch = 2.0 * math.pi * radius / layout.num_bars
        return pitch - db, pitch
    edge = section.cover + HOOP_DIAMETER + db / 2.0
    if section.b - 2.0 * edge <= 0.0 or section.h - 2.0 * edge <= 0.0:
        return None
    n_b, n_h = section.perimeter_bar_counts(layout.num_bars)
    pitches = ((section.b - 2.0 * edge) / (n_b - 1), (section.h - 2.0 * edge) / (n_h - 1))
    return min(pitches) - db, max(pitches)


def candidate_layouts(
    section: Section,
    max_ratio: float,
    min_ratio: float = MIN_RATIO,
    max_spacing: float = MAX_SUPPORTED_SPACING,
) -> List[LongitudinalLayout]:
    """
    Every buildable layout with min_ratio Ag <= Ast <= max_ratio Ag, by increasing area (then fewer bars).

    Adding bars only tightens the clear spacing, so a bar size stops at the first layout that violates it;
    the maximum center-to-center spacing ``max_spacing`` of rectangular layouts is met by adding bars.
    """
    ag = section.gross_area
    least = MIN_CIRCULAR_BARS if isinstance(section, CircularSection) else 4
    layouts: List[LongitudinalLayout] = []
    for size in COLUMN_BAR_SIZES:
        n = max(least, math.ceil(min_ratio * ag / BAR_DATABASE[size]["area"]))
        layout = LongitudinalLayout(n + n % 2, size)
        while layout.area <= max_ratio * ag:
            spacings = _bar_spacings(section, layout)
            if spacings is None or spacings[0] < _min_clear_spacing(size):
                break
            if isinstance(section, CircularSection) or spacings[1] <= max_spacing:
                layouts.append(layout)
            layout = LongitudinalLayout(layout.num_bars + 2, size)
    if not layouts:
        raise ValueError(
            f"Column section of {ag:.1f} in^2 with {section.cover:g} in clear cover cannot hold longitudinal bars "
            f"between {min_ratio:.0%} and {max_ratio:.0%} of Ag with the ACI 318-25 §25.2.3 clear spacing and a bar "
            f"spacing of at most {max_spacing:g} in."
        )
    return sorted(layouts, key=lambda lay: lay.weight_order)


def apply_layout(section: Section, layout: LongitudinalLayout, steel: Steel) -> None:
    """Place ``layout`` in ``section`` (replacing its longitudinal bars)."""
    if isinstance(section, CircularSection):
        section.setup_circular_bar_pattern(layout.num_bars, layout.bar_size, tie_bar_size="#4", steel=steel)
    else:
        section.setup_perimeter_bar_pattern(layout.num_bars, layout.bar_size, tie_bar_size="#4", steel=steel)


def lightest_layout(
    layouts: Sequence[LongitudinalLayout], adequate: Callable[[LongitudinalLayout], bool]
) -> Optional[LongitudinalLayout]:
    """
    Lightest layout of ``layouts`` (then fewest bars) for which ``adequate`` holds, or None.

    ``adequate`` must be monotone within a bar size: two more bars of one size never remove a bar from a
    face, so strength grows with the bar count. Across sizes it need not grow with the area (the bars sit
    differently), so each size is bisected on its own, over the layouts lighter than the best found so far.
    """
    best: Optional[LongitudinalLayout] = None
    for size in COLUMN_BAR_SIZES:
        series = sorted(
            (lay for lay in layouts if lay.bar_size == size and (best is None or lay.weight_order < best.weight_order)),
            key=lambda lay: lay.weight_order,
        )
        if not series or not adequate(series[-1]):
            continue
        lo, hi = -1, len(series) - 1  # series[lo] inadequate (or none), series[hi] adequate
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if adequate(series[mid]):
                hi = mid
            else:
                lo = mid
        best = series[hi]
    return best


def check_layout(
    section: Section,
    layout: LongitudinalLayout,
    load_sets: Sequence[LoadEffects],
    code: DesignCode,
    steel: Steel,
    member_id: str = "column-01",
    fy_shear: float = 60.0,
) -> ColumnDesignResult:
    """Place ``layout`` in ``section`` and check the column (axial, P-M interaction, shear with ties of yield
    strength ``fy_shear``, ksi) for ``load_sets``."""
    apply_layout(section, layout, steel)
    return Column(section=section, code=code, member_id=member_id, required_steel=layout.area,
                  fy_shear=fy_shear).design(load_sets)


def design_longitudinal_reinforcement(
    section: Section,
    load_sets: Sequence[LoadEffects],
    code: DesignCode,
    steel: Steel,
    max_ratio: float,
    member_id: str = "column-01",
    max_spacing: float = MAX_SUPPORTED_SPACING,
    fy_shear: float = 60.0,
) -> ColumnReinforcementDesign:
    """
    Lightest candidate layout whose axial and P-M strength carry every load set (``lightest_layout``);
    the layout is left on ``section``.

    The minimum-ratio layout is checked first; it usually suffices. If no layout is adequate, the
    heaviest is kept and the result reports the failing ratio.
    """
    layouts = candidate_layouts(section, max_ratio, max_spacing=max_spacing)
    results: Dict[LongitudinalLayout, ColumnDesignResult] = {}

    def strong_enough(layout: LongitudinalLayout) -> bool:
        if layout not in results:
            results[layout] = check_layout(section, layout, load_sets, code, steel, member_id, fy_shear)
        return results[layout].axial_flexure.demand_capacity_ratio <= 1.0

    chosen = layouts[0] if strong_enough(layouts[0]) else lightest_layout(layouts[1:], strong_enough)
    if chosen is None:
        heaviest = layouts[-1]
        strong_enough(heaviest)
        result = results[heaviest]
        note = (f"Longitudinal steel at the {max_ratio:.0%} limit ({heaviest}) does not provide the axial-flexural "
                "strength; a larger section is needed.")
        result.messages.append(note)
        result.axial_flexure.messages.append(note)
        apply_layout(section, heaviest, steel)
        return ColumnReinforcementDesign(heaviest, result, False)
    apply_layout(section, chosen, steel)
    return ColumnReinforcementDesign(chosen, results[chosen], True)
