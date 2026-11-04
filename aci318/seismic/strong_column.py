"""
Column longitudinal bars for strong-column/weak-beam (ACI 318-25 §18.7.3.2), special moment frames.

Column bars are first designed for strength (``aci318.members.column_reinforcement``). Where a joint then
has sum(Mnc) < 1.2 sum(Mnb), every column framing the joint is given the lightest heavier candidate layout
whose Mn (lowest over its factored axial forces, weaker axis, as 18.7.3.2 counts it) reaches its share of
the deficit: its current Mn times 1.2 sum(Mnb) / sum(Mnc), the largest over its failing joints. Raising a
column changes the sums at both of its joints, so passes repeat until every joint satisfies the
requirement, or no column at a failing joint can take more steel within the 18.7.4.1 limit (the joint
check then reports the shortfall).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Mapping, Optional, Sequence

from aci318.codes.base import DesignCode
from aci318.materials.steel import Steel
from aci318.members.column_reinforcement import LongitudinalLayout, apply_layout, lightest_layout
from aci318.sections.rectangle import RectangleSection
from aci318.seismic.moment_frames import (
    FrameBeam,
    FrameColumn,
    FrameJoint,
    column_strength_for_strong_column,
    strong_column_demand,
)

MAX_PASSES = 20


def current_layout(column: FrameColumn) -> LongitudinalLayout:
    """Layout of a perimeter-barred frame column."""
    n_b, n_h = column.bars_per_face
    return LongitudinalLayout(2 * n_b + 2 * n_h - 4, column.bar_size)


def with_layout(column: FrameColumn, layout: LongitudinalLayout, steel: Optional[Steel] = None) -> FrameColumn:
    """Copy of ``column`` reinforced with ``layout`` of ``steel`` (default: the steel of its current bars; its own
    section; ``column`` is unchanged)."""
    if steel is None:
        steel = column.section.bar_pattern[5]
    section = RectangleSection(b=column.section.b, h=column.section.h, concrete=column.section.concrete,
                               cover=column.section.cover)
    apply_layout(section, layout, steel)
    return replace(column, section=section, bars_per_face=section.bar_pattern[:2], bar_size=layout.bar_size)


def proportion_for_strong_column(
    joints: Sequence[FrameJoint],
    beams: Dict[str, FrameBeam],
    columns: Dict[str, FrameColumn],
    code: DesignCode,
    layouts: Mapping[str, Sequence[LongitudinalLayout]],
    steel: Optional[Steel] = None,
) -> Dict[str, LongitudinalLayout]:
    """
    Raise the bars of columns at joints failing 18.7.3.2; ``columns`` is updated in place with the new
    layouts (each FrameColumn is replaced by a copy). ``layouts`` holds the candidate layouts of each
    column (ascending, within the 18.7.4.1 limit). The new bars are of ``steel``, by default each column's own.
    Returns the new layout of every raised column.
    """
    raised: Dict[str, LongitudinalLayout] = {}
    for _ in range(MAX_PASSES):
        targets: Dict[str, float] = {}
        for joint in joints:
            for direction in joint.beams:
                demand = strong_column_demand(joint, direction, beams, columns, code)
                if demand is None or demand[1] >= demand[0]:
                    continue
                scale = demand[0] / max(demand[1], 1e-9)
                for cid in (joint.column_below, joint.column_above):
                    if cid in columns:
                        need = scale * column_strength_for_strong_column(columns[cid], code)
                        targets[cid] = max(targets.get(cid, 0.0), need)

        progressed = False
        for cid, target in targets.items():
            column = columns[cid]
            heavier: List[LongitudinalLayout] = [
                lay for lay in layouts[cid] if lay.weight_order > current_layout(column).weight_order
            ]
            if not heavier:
                continue  # already at the steel limit

            def reaches(layout: LongitudinalLayout) -> bool:
                return column_strength_for_strong_column(with_layout(column, layout, steel), code) >= target

            choice = lightest_layout(heavier, reaches) or max(heavier, key=lambda lay: lay.weight_order)
            columns[cid] = with_layout(column, choice, steel)
            raised[cid] = choice
            progressed = True
        if not progressed:
            break
    return raised
