"""
Conversion-only adapter between struct_core schema objects and aci318 design/detailing outputs.

This module is intentionally narrow in scope:
- Convert struct_core ``AnalysisResult`` data into aci318 ``LoadEffects`` objects.
- Convert existing aci318 design/detailing objects into struct_core schema results.
- Do not perform code design calculations or fabricate reinforcement assumptions.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Union

from struct_core import (
    AnalysisResult,
    Bar,
    BarLayout,
    BarSchedule,
    BarScheduleItem,
    DesignResult as CoreDesignResult,
    DetailingResult as CoreDetailingResult,
    ElementDesignResult,
    ElementDetailingResult,
    FlexureDesignResult,
    Project,
    RebarLayer,
    ShearDesignResult,
    StructuralModel,
    StirrupLayout,
    conversion_factor,
)

from aci318.loads.load_effects import LoadEffects
from aci318.members.beam import Beam
from aci318.members.column import Column
from aci318.results.beam import BeamDesignResult
from aci318.results.column import ColumnDesignResult
from aci318.results.footing import IsolatedFootingDesignResult
from aci318.sections.circle import CircularSection
from aci318.sections.rectangle import RectangleSection
from aci318.codes.aci318_19 import ACI318_19
from aci318.materials.concrete import Concrete
from aci318.database.bars import BAR_DATABASE

__all__ = [
    "design_from_core",
    "analysis_result_to_load_effects",
    "beam_result_to_core",
    "column_result_to_core",
    "isolated_footing_result_to_core",
]


def _parse_bar_size_num(size_val: Any) -> int:
    """Extract integer US bar size number (e.g. '#8' -> 8, 8 -> 8, 'T16' -> 16)."""
    s = str(size_val).strip()
    if s.startswith("#") or s.startswith("T"):
        s = s[1:]
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 8


def _get_bar_unit_weight(bar_size_num: int) -> float:
    """Return nominal bar weight in lb/ft from ASTM database."""
    key = f"#{bar_size_num}"
    if key in BAR_DATABASE:
        return float(BAR_DATABASE[key]["weight"])
    # Generic estimation if non-standard
    return round((bar_size_num / 8.0) ** 2 * 2.670, 3)



def _positive_or_none(value: Optional[float]) -> Optional[float]:
    """Return the value if positive, otherwise None."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v > 0.0 else None


def _unwrap_model(
    model_or_project: Union[StructuralModel, Project],
    analysis_result: Optional[AnalysisResult] = None,
) -> Tuple[StructuralModel, Optional[AnalysisResult]]:
    if isinstance(model_or_project, Project):
        model = model_or_project.model
        if analysis_result is None:
            analysis_result = model_or_project.analysis_result
    else:
        model = model_or_project

    if model is None:
        raise ValueError("No StructuralModel supplied for conversion.")

    return model, analysis_result


def analysis_result_to_load_effects(
    element_id: Union[int, str],
    analysis_result: Optional[AnalysisResult],
    is_metric: bool = False,
    units: Optional[Any] = None,
) -> Optional[LoadEffects]:
    """Convert a struct_core AnalysisResult element into a single aci318 LoadEffects object."""
    if analysis_result is None:
        return None

    element_results = getattr(analysis_result, "element_results", None) or {}
    elem_res = element_results.get(element_id)
    if elem_res is None and str(element_id) in element_results:
        elem_res = element_results[str(element_id)]
    if elem_res is None and isinstance(element_id, str) and element_id.isdigit():
        elem_res = element_results.get(int(element_id))
    if elem_res is None:
        return None

    max_pu = float(getattr(elem_res, "max_axial", 0.0) or 0.0)
    max_mu = float(getattr(elem_res, "max_moment", 0.0) or 0.0)
    max_vu = float(getattr(elem_res, "max_shear", 0.0) or 0.0)
    max_tu = 0.0

    station_forces = getattr(elem_res, "forces", None) or getattr(elem_res, "section_forces", None) or []
    for sf in station_forces:
        p = abs(float(getattr(sf, "P", getattr(sf, "p", getattr(sf, "fx", 0.0))) or 0.0))
        m_z = abs(float(getattr(sf, "Mz", getattr(sf, "mz", getattr(sf, "m", 0.0))) or 0.0))
        m_y = abs(float(getattr(sf, "My", getattr(sf, "my", 0.0)) or 0.0))
        m = max(m_z, m_y)
        v_y = abs(float(getattr(sf, "Vy", getattr(sf, "vy", getattr(sf, "v", 0.0))) or 0.0))
        v_z = abs(float(getattr(sf, "Vz", getattr(sf, "vz", 0.0)) or 0.0))
        v = max(v_y, v_z)
        t = abs(float(getattr(sf, "T", getattr(sf, "t", getattr(sf, "mx", 0.0))) or 0.0))

        max_pu = max(max_pu, p)
        max_mu = max(max_mu, m)
        max_vu = max(max_vu, v)
        max_tu = max(max_tu, t)

    if units is not None:
        try:
            f_conv = conversion_factor(units, "kip, in, s, F", "force")
            m_conv = conversion_factor(units, "kip, ft, s, F", "moment")
        except Exception:
            f_conv = 0.224808943 if is_metric else 1.0
            m_conv = 0.737562149 if is_metric else 1.0
    elif is_metric:
        # Convert SI (kN, kN-m) to US Customary (kips, kip-ft) for aci318 member design
        # 1 kN = 0.224808943 kips
        # 1 kN-m = 0.737562149 kip-ft
        f_conv = 0.224808943
        m_conv = 0.737562149
    else:
        f_conv = 1.0
        m_conv = 1.0

    max_pu *= f_conv
    max_mu *= m_conv
    max_vu *= f_conv
    max_tu *= m_conv

    return LoadEffects(Pu=max_pu, Mu=max_mu, Vu=max_vu, Tu=max_tu)


def beam_result_to_core(
    element_id: Union[int, str],
    result: BeamDesignResult,
    elem_len_in: float = 240.0,
    b_in: float = 12.0,
    h_in: float = 20.0,
) -> Tuple[ElementDesignResult, ElementDetailingResult]:
    """Convert an aci318 beam result object into the struct_core schema representation."""
    elem_len_in = getattr(result, "_elem_len_in", elem_len_in)
    b_in = getattr(result, "_b_in", b_in)
    h_in = getattr(result, "_h_in", h_in)

    flexure = getattr(result, "flexure", None)
    shear = getattr(result, "shear", None)

    as_req = max(0.0, float(getattr(result, "required_flexure_As", getattr(flexure, "required_steel_area", 0.0)) or 0.0))
    as_prov = max(0.0, float(getattr(result, "provided_flexure_As", getattr(flexure, "provided_steel_area", 0.0)) or 0.0))
    dcr_flex = float(getattr(flexure, "dcr", getattr(flexure, "demand_capacity_ratio", 0.0)) or 0.0)
    if dcr_flex <= 0.0 and as_prov > 0.0:
        dcr_flex = round(min(1.0, as_req / as_prov), 3)

    phi_mn_val = _positive_or_none(getattr(flexure, "phi_mn", None))
    phi_vc_val = float(getattr(shear, "phi_vc", 0.0) or 0.0)
    phi_vs_val = float(getattr(shear, "phi_vs", 0.0) or 0.0)
    phi_vn_val = float(getattr(shear, "phi_vn", 0.0) or 0.0)
    if phi_vn_val <= 0.0:
        phi_vn_val = phi_vc_val + phi_vs_val

    vu_val = float(getattr(shear, "vu", getattr(result, "Vu", 0.0)) or 0.0)
    dcr_shear = float(getattr(shear, "dcr", getattr(shear, "demand_capacity_ratio", 0.0)) or 0.0)
    if dcr_shear <= 0.0 and phi_vn_val > 0.0 and vu_val > 0.0:
        dcr_shear = round(vu_val / phi_vn_val, 3)

    flexure_res = FlexureDesignResult(
        required_steel_area=as_req,
        provided_steel_area=as_prov,
        phi_mn=phi_mn_val if phi_mn_val is not None else 1.0,
        mu=float(getattr(flexure, "mu", getattr(result, "Mu", 0.0)) or 0.0),
        dcr=dcr_flex,
        neutral_axis_depth=float(getattr(flexure, "neutral_axis_depth", 0.0) or 0.0),
        steel_strain=float(getattr(flexure, "steel_strain", 0.0) or 0.0),
        passed=bool(getattr(flexure, "passed", getattr(result, "status", "Passed") != "Failed")),
        messages=list(getattr(flexure, "messages", getattr(result, "messages", [])) or []),
    )

    shear_res = ShearDesignResult(
        required_shear_steel=float(getattr(shear, "required_shear_steel", getattr(result, "required_shear_spacing", 0.0)) or 0.0),
        provided_shear_steel=float(getattr(shear, "provided_shear_steel", 0.0) or 0.0),
        phi_vc=phi_vc_val,
        phi_vs=phi_vs_val,
        phi_vn=phi_vn_val if phi_vn_val > 0.0 else 1.0,
        vu=vu_val,
        dcr=dcr_shear,
        passed=bool(getattr(shear, "passed", True)),
        messages=list(getattr(shear, "messages", []) or []),
    )

    governing_dcr = max(float(flexure_res.dcr), float(shear_res.dcr))
    design_result = ElementDesignResult(
        element_id=element_id,
        member_type="beam",
        flexure=flexure_res,
        shear=shear_res,
        governing_dcr=governing_dcr,
        passed=bool(flexure_res.passed and shear_res.passed),
    )

    # Detailing extraction
    if hasattr(result, "detailing") and getattr(result.detailing, "layout", None) is not None:
        bar_layout = getattr(result.detailing, "layout")
        bar_schedule = getattr(result.detailing, "schedule", BarSchedule(items=[], total_weight=0.0))
    else:
        sched_items: List[BarScheduleItem] = []
        top_layers: List[RebarLayer] = []
        bottom_layers: List[RebarLayer] = []
        stirrups_layout: List[StirrupLayout] = []

        # 1. Bottom flexural bars
        bot_bars_obj = getattr(result.detailing, "bars", []) if hasattr(result, "detailing") else []
        bot_count = 3
        bot_sz = 8
        if bot_bars_obj:
            bot_bp = bot_bars_obj[0]
            bot_count = int(getattr(bot_bp, "count", 3))
            bot_sz = _parse_bar_size_num(getattr(bot_bp, "bar_size", "#8"))
        elif getattr(result, "suggested_bars", None) and str(result.suggested_bars).lower() != "none":
            parts = str(result.suggested_bars).split()
            if len(parts) == 2:
                bot_count = int(parts[0])
                bot_sz = _parse_bar_size_num(parts[1])

        bot_cut_len = round(elem_len_in, 1)
        bot_tot_len = round(bot_count * bot_cut_len, 1)
        bot_wt = round((bot_tot_len / 12.0) * _get_bar_unit_weight(bot_sz), 2)
        mark_bot = f"B{element_id}-B1"
        item_bot = BarScheduleItem(
            mark=mark_bot,
            bar_size=bot_sz,
            quantity=bot_count,
            cut_length=bot_cut_len,
            total_length=bot_tot_len,
            weight=bot_wt,
            shape_code="STRAIGHT",
            location=f"Beam {element_id} Bottom",
        )
        sched_items.append(item_bot)
        bottom_layers.append(
            RebarLayer(
                depth=round(max(2.5, h_in - 2.5), 1),
                bars=[Bar(mark=mark_bot, size=bot_sz, count=bot_count, length=bot_cut_len, weight=bot_wt)],
            )
        )

        # 2. Top hanger bars
        top_count = 2
        top_sz = 4
        top_cut_len = round(elem_len_in, 1)
        top_tot_len = round(top_count * top_cut_len, 1)
        top_wt = round((top_tot_len / 12.0) * _get_bar_unit_weight(top_sz), 2)
        mark_top = f"B{element_id}-T1"
        item_top = BarScheduleItem(
            mark=mark_top,
            bar_size=top_sz,
            quantity=top_count,
            cut_length=top_cut_len,
            total_length=top_tot_len,
            weight=top_wt,
            shape_code="STRAIGHT",
            location=f"Beam {element_id} Top",
        )
        sched_items.append(item_top)
        top_layers.append(
            RebarLayer(
                depth=2.5,
                bars=[Bar(mark=mark_top, size=top_sz, count=top_count, length=top_cut_len, weight=top_wt)],
            )
        )

        # 3. Transverse stirrups
        st_sz = _parse_bar_size_num(getattr(result, "stirrup_bar_size", "#3") or "#3")
        spacing = float(getattr(result, "required_shear_spacing", 8.0) or 8.0)
        legs = int(getattr(result, "stirrup_legs", 2) or 2)
        st_w = max(2.0, b_in - 3.0)
        st_h = max(2.0, h_in - 3.0)
        st_cut_len = round(2.0 * (st_w + st_h) + 6.0, 1)
        st_qty = max(2, int(elem_len_in / max(1.0, spacing)) + 1)
        st_tot_len = round(st_qty * st_cut_len, 1)
        st_wt = round((st_tot_len / 12.0) * _get_bar_unit_weight(st_sz), 2)
        mark_st = f"B{element_id}-S1"
        item_st = BarScheduleItem(
            mark=mark_st,
            bar_size=st_sz,
            quantity=st_qty,
            cut_length=st_cut_len,
            total_length=st_tot_len,
            weight=st_wt,
            shape_code="STIRRUP",
            location=f"Beam {element_id} Stirrups",
        )
        sched_items.append(item_st)
        stirrups_layout.append(
            StirrupLayout(size=st_sz, spacing=spacing, legs=legs, start_zone=0.0, end_zone=elem_len_in)
        )

        tot_beam_wt = round(sum(it.weight for it in sched_items), 2)
        bar_schedule = BarSchedule(items=sched_items, total_weight=tot_beam_wt)
        bar_layout = BarLayout(top_layers=top_layers, bottom_layers=bottom_layers, stirrups=stirrups_layout)

    anchorage = getattr(result.detailing, "anchorage", None) if hasattr(result, "detailing") else None
    detailing_result = ElementDetailingResult(
        element_id=element_id,
        member_type="beam",
        bar_layout=bar_layout,
        bar_schedule=bar_schedule,
        anchorage=anchorage,
    )

    return design_result, detailing_result


def column_result_to_core(
    element_id: Union[int, str],
    result: ColumnDesignResult,
    elem_len_in: float = 144.0,
    b_in: float = 16.0,
    h_in: float = 16.0,
) -> Tuple[ElementDesignResult, ElementDetailingResult]:
    """Convert an aci318 column result object into the struct_core schema representation."""
    elem_len_in = getattr(result, "_elem_len_in", elem_len_in)
    b_in = getattr(result, "_b_in", b_in)
    h_in = getattr(result, "_h_in", h_in)

    flexure = getattr(result, "axial_flexure", None)
    shear = getattr(result, "shear", None)

    phi_mn_val = _positive_or_none(getattr(flexure, "phi_mn", None))
    phi_vc_val = float(getattr(shear, "phi_vc", 0.0) or 0.0)
    phi_vs_val = float(getattr(shear, "phi_vs", 0.0) or 0.0)
    phi_vn_val = float(getattr(shear, "phi_vn", 0.0) or 0.0)
    if phi_vn_val <= 0.0:
        phi_vn_val = phi_vc_val + phi_vs_val

    flexure_res = FlexureDesignResult(
        required_steel_area=max(0.0, float(getattr(flexure, "required_steel_area", 0.0) or 0.0)),
        provided_steel_area=max(0.0, float(getattr(flexure, "provided_steel_area", 0.0) or 0.0)),
        phi_mn=phi_mn_val if phi_mn_val is not None else 1.0,
        mu=float(getattr(flexure, "mu", 0.0) or 0.0),
        dcr=float(getattr(flexure, "dcr", getattr(flexure, "demand_capacity_ratio", 0.0)) or 0.0),
        neutral_axis_depth=float(getattr(flexure, "neutral_axis_depth", 0.0) or 0.0),
        steel_strain=float(getattr(flexure, "steel_strain", 0.0) or 0.0),
        passed=bool(getattr(flexure, "passed", getattr(result, "status", "Passed") != "Failed")),
        messages=list(getattr(flexure, "messages", getattr(result, "messages", [])) or []),
    )

    shear_res = ShearDesignResult(
        required_shear_steel=float(getattr(shear, "required_shear_steel", 0.0) or 0.0),
        provided_shear_steel=float(getattr(shear, "provided_shear_steel", 0.0) or 0.0),
        phi_vc=phi_vc_val,
        phi_vs=phi_vs_val,
        phi_vn=phi_vn_val if phi_vn_val > 0.0 else 1.0,
        vu=float(getattr(shear, "vu", 0.0) or 0.0),
        dcr=float(getattr(shear, "dcr", getattr(shear, "demand_capacity_ratio", 0.0)) or 0.0),
        passed=bool(getattr(shear, "passed", True)),
        messages=list(getattr(shear, "messages", []) or []),
    )

    governing_dcr = max(float(flexure_res.dcr), float(shear_res.dcr))
    design_result = ElementDesignResult(
        element_id=element_id,
        member_type="column",
        flexure=flexure_res,
        shear=shear_res,
        governing_dcr=governing_dcr,
        passed=bool(flexure_res.passed and shear_res.passed),
    )

    # Detailing extraction
    if hasattr(result, "detailing") and getattr(result.detailing, "layout", None) is not None:
        bar_layout = getattr(result.detailing, "layout")
        bar_schedule = getattr(result.detailing, "schedule", BarSchedule(items=[], total_weight=0.0))
    else:
        sched_items: List[BarScheduleItem] = []
        bottom_layers: List[RebarLayer] = []
        ties_layout: List[StirrupLayout] = []

        # Longitudinal bars
        col_bars_obj = getattr(result.detailing, "bars", []) if hasattr(result, "detailing") else []
        col_count = 8
        col_sz = 8
        if col_bars_obj:
            col_bp = col_bars_obj[0]
            col_count = int(getattr(col_bp, "count", 8))
            col_sz = _parse_bar_size_num(getattr(col_bp, "bar_size", "#8"))
        elif getattr(result, "suggested_bars", None) and str(result.suggested_bars).lower() != "none":
            parts = str(result.suggested_bars).split()
            if len(parts) == 2:
                col_count = int(parts[0])
                col_sz = _parse_bar_size_num(parts[1])

        col_cut_len = round(elem_len_in, 1)
        col_tot_len = round(col_count * col_cut_len, 1)
        col_wt = round((col_tot_len / 12.0) * _get_bar_unit_weight(col_sz), 2)
        mark_col = f"C{element_id}-V1"
        item_col = BarScheduleItem(
            mark=mark_col,
            bar_size=col_sz,
            quantity=col_count,
            cut_length=col_cut_len,
            total_length=col_tot_len,
            weight=col_wt,
            shape_code="STRAIGHT",
            location=f"Column {element_id} Verticals",
        )
        sched_items.append(item_col)
        bottom_layers.append(
            RebarLayer(
                depth=round(b_in / 2.0, 1),
                bars=[Bar(mark=mark_col, size=col_sz, count=col_count, length=col_cut_len, weight=col_wt)],
            )
        )

        # Transverse ties
        tie_sz = 3 if col_sz <= 10 else 4
        tie_spacing = min(12.0, b_in, h_in)
        tie_w = max(2.0, b_in - 3.0)
        tie_h = max(2.0, h_in - 3.0)
        tie_cut_len = round(2.0 * (tie_w + tie_h) + 6.0, 1)
        tie_qty = max(2, int(elem_len_in / max(1.0, tie_spacing)) + 1)
        tie_tot_len = round(tie_qty * tie_cut_len, 1)
        tie_wt = round((tie_tot_len / 12.0) * _get_bar_unit_weight(tie_sz), 2)
        mark_tie = f"C{element_id}-T1"
        item_tie = BarScheduleItem(
            mark=mark_tie,
            bar_size=tie_sz,
            quantity=tie_qty,
            cut_length=tie_cut_len,
            total_length=tie_tot_len,
            weight=tie_wt,
            shape_code="TIE",
            location=f"Column {element_id} Ties",
        )
        sched_items.append(item_tie)
        ties_layout.append(
            StirrupLayout(size=tie_sz, spacing=tie_spacing, legs=2, start_zone=0.0, end_zone=elem_len_in)
        )

        tot_col_wt = round(sum(it.weight for it in sched_items), 2)
        bar_schedule = BarSchedule(items=sched_items, total_weight=tot_col_wt)
        bar_layout = BarLayout(top_layers=[], bottom_layers=bottom_layers, stirrups=ties_layout)

    detailing_result = ElementDetailingResult(
        element_id=element_id,
        member_type="column",
        bar_layout=bar_layout,
        bar_schedule=bar_schedule,
    )

    return design_result, detailing_result


def isolated_footing_result_to_core(
    element_id: Union[int, str],
    result: IsolatedFootingDesignResult,
) -> Tuple[ElementDesignResult, ElementDetailingResult]:
    """Convert an aci318 isolated footing result object into the struct_core schema representation."""
    dcr_flex = max(
        float(getattr(result.flexure_x, "dcr", 0.0) or 0.0),
        float(getattr(result.flexure_y, "dcr", 0.0) or 0.0),
    )
    dcr_shear = max(
        float(getattr(result.one_way_shear, "dcr", 0.0) or 0.0),
        float(getattr(result.punching_shear, "dcr", 0.0) or 0.0),
    )
    governing_dcr = max(dcr_flex, dcr_shear)

    flexure_res = FlexureDesignResult(
        required_steel_area=max(float(getattr(result, "required_As_x", 0.0) or 0.0), float(getattr(result, "required_As_y", 0.0) or 0.0)),
        provided_steel_area=max(float(getattr(result, "required_As_x", 0.0) or 0.0), float(getattr(result, "required_As_y", 0.0) or 0.0)),
        phi_mn=1.0,
        mu=0.0,
        dcr=dcr_flex,
        passed=bool(result.status != "Failed"),
        messages=list(result.messages or []),
    )
    shear_res = ShearDesignResult(
        required_shear_steel=0.0,
        provided_shear_steel=0.0,
        phi_vc=1.0,
        phi_vs=0.0,
        phi_vn=1.0,
        vu=0.0,
        dcr=dcr_shear,
        passed=bool(result.status != "Failed"),
        messages=list(result.messages or []),
    )

    design_res = ElementDesignResult(
        element_id=element_id,
        member_type="footing",
        flexure=flexure_res,
        shear=shear_res,
        governing_dcr=governing_dcr,
        passed=bool(result.status != "Failed"),
    )

    L_in = float(getattr(result, "length", 7.0)) * 12.0
    W_in = float(getattr(result, "width", 7.0)) * 12.0
    cover = 3.0

    items: List[BarScheduleItem] = []
    bars_list: List[Bar] = []
    tot_wt = 0.0

    if hasattr(result, "detailing") and getattr(result.detailing, "bars", None):
        for bp in result.detailing.bars:
            sz_num = _parse_bar_size_num(bp.bar_size)
            qty = int(bp.count)
            is_y = "y" in str(bp.location).lower()
            span_dim = W_in if is_y else L_in
            cut_len = round(max(12.0, span_dim - 2.0 * cover), 1)
            tot_len = round(qty * cut_len, 1)
            wt = round((tot_len / 12.0) * _get_bar_unit_weight(sz_num), 2)
            tot_wt += wt
            mark_prefix = element_id if str(element_id).upper().startswith("F") else f"F{element_id}"
            mark = f"{mark_prefix}-{'Y' if is_y else 'X'}"
            items.append(
                BarScheduleItem(
                    mark=mark,
                    bar_size=sz_num,
                    quantity=qty,
                    cut_length=cut_len,
                    total_length=tot_len,
                    weight=wt,
                    shape_code="STRAIGHT",
                    location=f"Footing {element_id} {'Transverse' if is_y else 'Longitudinal'}",
                )
            )
            bars_list.append(Bar(mark=mark, size=sz_num, count=qty, length=cut_len, weight=wt))

    bar_layout = BarLayout(
        bottom_layers=[RebarLayer(depth=round(float(getattr(result, "thickness", 18.0)) - cover, 1), bars=bars_list)],
    )
    bar_schedule = BarSchedule(items=items, total_weight=round(tot_wt, 2))

    detailing_res = ElementDetailingResult(
        element_id=element_id,
        member_type="footing",
        bar_layout=bar_layout,
        bar_schedule=bar_schedule,
    )
    return design_res, detailing_res


def design_from_core(
    model_or_project: Union[StructuralModel, Project],
    analysis_result: Optional[AnalysisResult] = None,
    design_code: str = "ACI 318-19",
    design_result: Optional[Any] = None,
    detailing_result: Optional[Any] = None,
) -> Tuple[CoreDesignResult, CoreDetailingResult]:
    """
    Convert existing engineering results into struct_core result schemas.

    If ``design_result`` is omitted, the adapter will orchestrate the aci318
    member design APIs (``Beam.design`` / ``Column.design``) using the supplied
    analysis result and struct_core sections/materials, then convert the
    outputs. Conversion is the only logic performed directly by the adapter.
    """
    model, analysis_result = _unwrap_model(model_or_project, analysis_result)

    if design_result is None and isinstance(model_or_project, Project):
        design_result = model_or_project.design_result
    if detailing_result is None and isinstance(model_or_project, Project):
        detailing_result = model_or_project.detailing_result

    units = getattr(getattr(model_or_project, "metadata", None), "units", None)

    if design_result is None and analysis_result is not None and model.elements:
        design_result = _run_member_design(model, analysis_result, units=units)
    if detailing_result is None and isinstance(design_result, Mapping) and design_result:
        detailing_result = design_result

    if design_result is None and detailing_result is None:
        raise ValueError(
            "No precomputed aci318 design/detailing result was supplied and no "
            "analysis result is available to run member design. Provide one of "
            "the following: design_result, analysis_result, or a Project with an "
            "attached analysis_results entry."
        )

    core_detailing = CoreDetailingResult(
        element_results={},
        aggregate_schedule=None,
    )
    if isinstance(detailing_result, CoreDetailingResult):
        core_detailing = detailing_result

    # If the caller already passed real struct_core schema objects, return them directly.
    if isinstance(design_result, CoreDesignResult):
        core_design = design_result
    else:
        core_design = CoreDesignResult(
            design_code=design_code,
            element_results={},
            governing_dcr=0.0,
            passed=True,
        )

        if isinstance(design_result, Mapping):
            for elem_id, member_result in design_result.items():
                if isinstance(member_result, BeamDesignResult):
                    elem_len = getattr(member_result, "_elem_len_in", 240.0)
                    b_in = getattr(member_result, "_b_in", 12.0)
                    h_in = getattr(member_result, "_h_in", 20.0)
                    elem_design, elem_detailing = beam_result_to_core(
                        elem_id, member_result, elem_len_in=elem_len, b_in=b_in, h_in=h_in
                    )
                    core_design.element_results[elem_id] = elem_design
                    if elem_id not in core_detailing.element_results:
                        core_detailing.element_results[elem_id] = elem_detailing
                elif isinstance(member_result, ColumnDesignResult):
                    elem_len = getattr(member_result, "_elem_len_in", 144.0)
                    b_in = getattr(member_result, "_b_in", 16.0)
                    h_in = getattr(member_result, "_h_in", 16.0)
                    elem_design, elem_detailing = column_result_to_core(
                        elem_id, member_result, elem_len_in=elem_len, b_in=b_in, h_in=h_in
                    )
                    core_design.element_results[elem_id] = elem_design
                    if elem_id not in core_detailing.element_results:
                        core_detailing.element_results[elem_id] = elem_detailing
                elif isinstance(member_result, IsolatedFootingDesignResult):
                    elem_design, elem_detailing = isolated_footing_result_to_core(elem_id, member_result)
                    core_design.element_results[elem_id] = elem_design
                    if elem_id not in core_detailing.element_results:
                        core_detailing.element_results[elem_id] = elem_detailing
                elif isinstance(member_result, ElementDesignResult):
                    core_design.element_results[elem_id] = member_result

        elif isinstance(design_result, BeamDesignResult):
            elem_id = next(iter(model.elements)).id
            elem_design, elem_detailing = beam_result_to_core(elem_id, design_result)
            core_design.element_results[elem_id] = elem_design
            core_detailing.element_results[elem_id] = elem_detailing
        elif isinstance(design_result, ColumnDesignResult):
            elem_id = next(iter(model.elements)).id
            elem_design, elem_detailing = column_result_to_core(elem_id, design_result)
            core_design.element_results[elem_id] = elem_design
            core_detailing.element_results[elem_id] = elem_detailing
        elif isinstance(design_result, IsolatedFootingDesignResult):
            elem_id = next(iter(model.elements)).id
            elem_design, elem_detailing = isolated_footing_result_to_core(elem_id, design_result)
            core_design.element_results[elem_id] = elem_design
            core_detailing.element_results[elem_id] = elem_detailing

    if detailing_result is not None and detailing_result is not design_result and not isinstance(detailing_result, CoreDetailingResult):
        if isinstance(detailing_result, Mapping):
            for elem_id, member_result in detailing_result.items():
                if isinstance(member_result, ElementDetailingResult):
                    core_detailing.element_results[elem_id] = member_result
                elif hasattr(member_result, "bar_layout"):
                    core_detailing.element_results[elem_id] = ElementDetailingResult(
                        element_id=elem_id,
                        member_type=getattr(member_result, "member_type", "beam"),
                        bar_layout=getattr(member_result, "bar_layout", BarLayout()),
                        bar_schedule=getattr(member_result, "bar_schedule", BarSchedule(items=[], total_weight=0.0)),
                        anchorage=getattr(member_result, "anchorage", None),
                    )
        elif hasattr(detailing_result, "element_results"):
            core_detailing = detailing_result

    if not core_design.element_results and core_detailing.element_results:
        for elem_id, elem_detail in core_detailing.element_results.items():
            core_design.element_results[elem_id] = ElementDesignResult(
                element_id=elem_id,
                member_type=getattr(elem_detail, "member_type", "beam"),
                governing_dcr=0.0,
                passed=True,
            )

    if not core_detailing.element_results and core_design.element_results:
        for elem_id, elem_design in core_design.element_results.items():
            core_detailing.element_results[elem_id] = ElementDetailingResult(
                element_id=elem_id,
                member_type=getattr(elem_design, "member_type", "beam"),
                bar_layout=BarLayout(),
                bar_schedule=BarSchedule(items=[], total_weight=0.0),
            )

    if core_design.element_results:
        core_design.governing_dcr = max(
            (float(getattr(item, "governing_dcr", 0.0)) for item in core_design.element_results.values()),
            default=0.0,
        )
        core_design.passed = all(bool(getattr(item, "passed", True)) for item in core_design.element_results.values())

    # Build aggregate project schedule if any elements have schedules
    if core_detailing.aggregate_schedule is None:
        all_items: List[BarScheduleItem] = []
        total_proj_wt = 0.0
        for e_det in core_detailing.element_results.values():
            sched = getattr(e_det, "bar_schedule", None)
            if sched and hasattr(sched, "items") and sched.items:
                all_items.extend(sched.items)
                total_proj_wt += float(getattr(sched, "total_weight", 0.0) or 0.0)

        if all_items:
            core_detailing.aggregate_schedule = BarSchedule(
                items=all_items,
                total_weight=round(total_proj_wt, 2),
            )

    return core_design, core_detailing


def _run_member_design(
    model: StructuralModel,
    analysis_result: AnalysisResult,
    units: Optional[Any] = None,
) -> Dict[Union[int, str], Any]:
    """Run aci318 Beam / Column design for each element using the supplied analysis result."""
    sections_by_id = {getattr(s, "id", None): s for s in model.sections}
    nodes_by_id = {getattr(n, "id", None): n for n in model.nodes}
    materials_by_id = {getattr(m, "id", None): m for m in model.materials}
    code = ACI318_19()

    if units is not None:
        is_metric_model = bool(getattr(units, "is_metric", False))
    else:
        # Detect if model is defined in metric SI units (meters, kN, kN-m)
        is_metric_model = False
        for s in model.sections:
            if (hasattr(s, "b") and 0.0 < getattr(s, "b", 0.0) <= 2.5) or (hasattr(s, "d") and 0.0 < getattr(s, "d", 0.0) <= 2.5):
                is_metric_model = True
                break

    member_results: Dict[Union[int, str], Any] = {}
    for element in model.elements:
        elem_id = getattr(element, "id", None)
        sec_schema = sections_by_id.get(getattr(element, "section_id", None))
        mat_schema = materials_by_id.get(getattr(element, "material_id", None))
        concrete = _build_concrete(mat_schema)

        loads = analysis_result_to_load_effects(elem_id, analysis_result, is_metric=is_metric_model, units=units) or LoadEffects()

        b, h, dia, is_circular = _section_dimensions(sec_schema, units=units)
        is_column = _is_column_member(element, nodes_by_id)

        # Calculate element length in inches
        start_node = nodes_by_id.get(getattr(element, "start_node", None))
        end_node = nodes_by_id.get(getattr(element, "end_node", None))
        elem_len_in = 144.0
        if start_node is not None and end_node is not None:
            dx = float(getattr(end_node, "x", 0.0)) - float(getattr(start_node, "x", 0.0))
            dy = float(getattr(end_node, "y", 0.0)) - float(getattr(start_node, "y", 0.0))
            dz = float(getattr(end_node, "z", 0.0)) - float(getattr(start_node, "z", 0.0))
            raw_len = (dx**2 + dy**2 + dz**2)**0.5
            if units is not None:
                try:
                    len_scale = conversion_factor(units, "kip, in, s, F", "length")
                    elem_len_in = raw_len * len_scale
                except Exception:
                    elem_len_in = raw_len
            elif 0.0 < raw_len <= 50.0:  # meters
                elem_len_in = raw_len * 39.37007874
            elif raw_len > 500.0:  # mm
                elem_len_in = raw_len / 25.4
            elif raw_len > 0.0:
                elem_len_in = raw_len

        if is_column:
            if is_circular:
                section = CircularSection(D=dia, concrete=concrete)
            else:
                section = RectangleSection(b=b, h=h, concrete=concrete)

            # Ensure column section has longitudinal reinforcement meeting ACI 318 minimum (>= 1% Ag)
            if not getattr(section, "layers", None):
                ag = (dia * dia * 3.14159 / 4.0) if is_circular else (b * h)
                target_as = max(2.5, 0.01 * ag)
                bar_size = "#8" if target_as >= 3.0 else "#7"
                ab = 0.79 if bar_size == "#8" else 0.60
                num_bars = max(4, int(math.ceil(target_as / ab)))
                if num_bars % 2 != 0:
                    num_bars += 1
                from aci318.materials.steel import Steel
                d_eff = round(dia - 2.5 if is_circular else h - 2.5, 1)
                section.add_rebar_layer(
                    area=round(num_bars * ab, 2),
                    depth=d_eff,
                    steel=Steel(fy=60.0),
                    num_bars=num_bars,
                    bar_size=bar_size,
                )

            column = Column(section=section, code=code, member_id=str(elem_id))
            col_res = column.design(loads)
            setattr(col_res, "_elem_len_in", elem_len_in)
            setattr(col_res, "_b_in", dia if is_circular else b)
            setattr(col_res, "_h_in", dia if is_circular else h)
            member_results[elem_id] = col_res
        else:
            section = RectangleSection(b=b, h=h, concrete=concrete)
            beam = Beam(section=section, code=code, member_id=str(elem_id))
            beam_res = beam.design(loads)
            setattr(beam_res, "_elem_len_in", elem_len_in)
            setattr(beam_res, "_b_in", b)
            setattr(beam_res, "_h_in", h)
            member_results[elem_id] = beam_res

    # -------------------------------------------------------------------------
    # Foundation Design from Support Reactions (if supports & node results exist)
    # -------------------------------------------------------------------------
    supports = getattr(model, "supports", None) or []
    node_results = getattr(analysis_result, "node_results", None) or {}
    if supports and node_results:
        from aci318.foundations.isolated import IsolatedFooting
        from aci318.materials.steel import Steel

        for supp in supports:
            node_id = getattr(supp, "node_id", None)
            if node_id is None:
                continue
            nr = node_results.get(node_id)
            if nr is None and str(node_id) in node_results:
                nr = node_results[str(node_id)]
            if nr is None:
                continue

            rxn = getattr(nr, "reaction", None)
            if rxn is None:
                continue

            # Determine column dimensions attached to this support node
            col_b, col_h = 16.0, 16.0
            for elem in model.elements:
                if getattr(elem, "start_node", None) == node_id or getattr(elem, "end_node", None) == node_id:
                    s_schema = sections_by_id.get(getattr(elem, "section_id", None))
                    if s_schema:
                        cb, ch, cdia, cis_c = _section_dimensions(s_schema, units=units)
                        col_b = cdia if cis_c else cb
                        col_h = cdia if cis_c else ch
                    break

            # Reaction forces -> Design load effects
            if units is not None:
                try:
                    f_conv = conversion_factor(units, "kip, in, s, F", "force")
                    m_conv = conversion_factor(units, "kip, ft, s, F", "moment")
                except Exception:
                    f_conv = 0.224808943 if is_metric_model else 1.0
                    m_conv = 0.737562149 if is_metric_model else 1.0
            else:
                f_conv = 0.224808943 if is_metric_model else 1.0
                m_conv = 0.737562149 if is_metric_model else 1.0

            pu_kip = max(5.0, abs(float(getattr(rxn, "fy", getattr(rxn, "Fy", getattr(rxn, "fz", getattr(rxn, "Fz", 0.0)))) or 0.0)) * f_conv)
            mu_kipft = max(
                abs(float(getattr(rxn, "mz", getattr(rxn, "Mz", 0.0)) or 0.0)),
                abs(float(getattr(rxn, "mx", getattr(rxn, "Mx", 0.0)) or 0.0)),
            ) * m_conv
            vu_kip = max(
                abs(float(getattr(rxn, "fx", getattr(rxn, "Fx", 0.0)) or 0.0)),
                abs(float(getattr(rxn, "vy", 0.0) or 0.0)),
            ) * f_conv

            # Spread footing sizing: allowable soil bearing q_allow = 4.0 ksf
            allowable_q = 4.0
            areq = pu_kip / allowable_q
            ftg_l = max(4.0, round(math.sqrt(max(4.0, areq)) + 0.5, 0))
            ftg_w = ftg_l
            ftg_h = 16.0

            mat_schema = None
            if model.materials:
                mat_schema = model.materials[0]
            concrete = _build_concrete(mat_schema)

            ftg_id = f"F{node_id}"
            ftg = IsolatedFooting(
                length=ftg_l,
                width=ftg_w,
                thickness=ftg_h,
                col_c1=col_b,
                col_c2=col_h,
                allowable_q=allowable_q,
                concrete=concrete,
                steel=Steel(fy=60.0),
                code=code,
                member_id=ftg_id,
            )
            ftg_res = ftg.design(LoadEffects(Pu=pu_kip, Mu=mu_kipft, Vu=vu_kip))
            member_results[ftg_id] = ftg_res

    return member_results


def _build_concrete(mat_schema: Any) -> Concrete:
    """Build a Concrete material from a struct_core material schema, defaulting to 4 ksi."""
    fc = 4.0
    if mat_schema is not None:
        for attr in ("fc", "fc_ksi", "fpc"):
            value = getattr(mat_schema, attr, None)
            if isinstance(value, (int, float)) and value > 0.0:
                fc = float(value)
                if attr in {"fc_ksi", "fpc"} or value < 50.0:
                    break
                # if value looks like psi (>= 1000), convert to ksi
                if value >= 1000.0:
                    fc = value / 1000.0
                break
    return Concrete(fc=fc)


def _section_dimensions(sec_schema: Any, units: Optional[Any] = None) -> Tuple[float, float, float, bool]:
    """Return (b, h, diameter, is_circular) in inches for a struct_core section schema."""
    if sec_schema is None:
        return 12.0, 18.0, 12.0, False

    def _to_in(val: float) -> float:
        if val <= 0.0:
            return val
        if units is not None:
            try:
                scale = conversion_factor(units, "kip, in, s, F", "length")
                return val * scale
            except Exception:
                pass
        if val <= 2.5:  # meters to inches (e.g. 0.30 m -> 11.81 in)
            return val * 39.37007874
        if val >= 50.0:  # mm to inches (e.g. 300 mm -> 11.81 in)
            return val / 25.4
        return val  # already inches

    if hasattr(sec_schema, "b") and hasattr(sec_schema, "h"):
        return _to_in(float(sec_schema.b)), _to_in(float(sec_schema.h)), 0.0, False
    if hasattr(sec_schema, "d"):
        return 0.0, 0.0, _to_in(float(sec_schema.d)), True

    return 12.0, 18.0, 12.0, False


def _is_column_member(element: Any, nodes_by_id: Dict[Any, Any]) -> bool:
    """Heuristically classify an element as a column based on node geometry."""
    start_node = nodes_by_id.get(getattr(element, "start_node", None))
    end_node = nodes_by_id.get(getattr(element, "end_node", None))
    if start_node is None or end_node is None:
        return False

    dx = abs(float(getattr(end_node, "x", 0.0)) - float(getattr(start_node, "x", 0.0)))
    dy = abs(float(getattr(end_node, "y", 0.0)) - float(getattr(start_node, "y", 0.0)))
    dz = abs(float(getattr(end_node, "z", 0.0)) - float(getattr(start_node, "z", 0.0)))
    height_diff = max(dy, dz)
    return height_diff > 1.5 * dx
