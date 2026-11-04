"""
Conversion-only adapter between struct_core schema objects and aci318 design/detailing outputs.

This module is intentionally narrow in scope:
- Convert struct_core ``AnalysisResult`` data into aci318 ``LoadEffects`` objects.
- Convert existing aci318 design/detailing objects into struct_core schema results.
- Do not perform code design calculations or fabricate reinforcement assumptions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from struct_core.detailing_result.anchorage import Anchorage, LapSplice
from struct_core import (
    AnalysisResult,
    ElementResult,
    Bar,
    BarLayout,
    BarSchedule,
    BarScheduleItem,
    CodeCheckResult,
    DesignInputs,
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
    parse_units,
)
from struct_core.units import PRESETS

from aci318.loads.load_effects import LoadEffects
from aci318.members.beam import Beam
from aci318.members.column_reinforcement import (
    design_longitudinal_reinforcement,
    max_longitudinal_ratio,
    max_supported_bar_spacing,
)
from aci318.results.beam import BeamDesignResult
from aci318.results.column import ColumnDesignResult
from aci318.results.footing import IsolatedFootingDesignResult
from aci318.sections.circle import CircularSection
from aci318.sections.rectangle import RectangleSection
from aci318.codes.aci318_19 import ACI318_19
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.database.bars import BAR_DATABASE

__all__ = [
    "design_from_core",
    "analysis_result_to_load_effects",
    "analysis_result_to_load_sets",
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
            # If multiple analysis results (e.g. load combinations) are present and no single case is selected,
            # synthesize the governing envelope across all combinations for code design.
            if (
                model_or_project.analysis_results
                and not model_or_project.active_analysis_case
                and not any(str(k).lower() == "envelope" for k in model_or_project.analysis_results)
                and len(model_or_project.analysis_results) > 1
            ):
                from struct_core.analysis_result.superposition import envelope_results
                primary_ids = {lc.id for lc in (getattr(model, "load_cases", None) or [])}
                combos = [res for k, res in model_or_project.analysis_results.items() if k not in primary_ids]
                results_to_envelope = combos if combos else list(model_or_project.analysis_results.values())
                analysis_result = envelope_results(results_to_envelope)
            else:
                analysis_result = model_or_project.analysis_result
    else:
        model = model_or_project

    if model is None:
        raise ValueError("No StructuralModel supplied for conversion.")

    return model, analysis_result


def _find_element_result(element_id: Union[int, str], analysis_result: AnalysisResult) -> Optional[ElementResult]:
    element_results = getattr(analysis_result, "element_results", None) or {}
    elem_res = element_results.get(element_id)
    if elem_res is None and str(element_id) in element_results:
        elem_res = element_results[str(element_id)]
    if elem_res is None and isinstance(element_id, str) and element_id.isdigit():
        elem_res = element_results.get(int(element_id))
    return elem_res


def analysis_result_to_load_sets(
    element_id: Union[int, str],
    analysis_result: Optional[AnalysisResult],
    is_metric: bool = False,
    units: Optional[Any] = None,
) -> Optional[List[LoadEffects]]:
    """
    Convert a struct_core element result into concurrent aci318 load sets.

    One LoadEffects object is produced per load combination and station, so the axial force and
    the moments of a set act together (ACI 318 §22.4 P-M interaction). Combinations come from
    ``ElementResult.combination_forces`` (filled by ``envelope_results``); a single-case result
    supplies its own station forces. Axial force is converted from the solver convention
    (tension positive) to the aci318 convention (compression positive). Local axis 3 (M3, V2)
    is the major bending axis, local axis 2 (M2, V3) the minor one.
    """
    if analysis_result is None:
        return None
    elem_res = _find_element_result(element_id, analysis_result)
    if elem_res is None:
        return None

    if units is not None:
        f_conv = conversion_factor(units, PRESETS["kip, in, s, °F"], "force")
        m_conv = conversion_factor(units, PRESETS["kip, in, s, °F"], "moment")
    elif is_metric:
        # Standard SI (kN, kN-m) to US Customary (kips, kip-in)
        f_conv = conversion_factor(PRESETS["kN, m, s, °C"], PRESETS["kip, in, s, °F"], "force")
        m_conv = conversion_factor(PRESETS["kN, m, s, °C"], PRESETS["kip, in, s, °F"], "moment")
    else:
        f_conv = 1.0
        m_conv = 1.0

    profiles = list(elem_res.combination_forces.values()) or ([elem_res.forces] if elem_res.forces else [])
    if not profiles:
        # Axial-only element without station forces
        return [
            LoadEffects(
                Pu=-float(elem_res.max_axial or 0.0) * f_conv,
                Mu=abs(float(elem_res.max_moment or 0.0)) * m_conv,
                Vu=abs(float(elem_res.max_shear or 0.0)) * f_conv,
            )
        ]

    load_sets: List[LoadEffects] = []
    for stations in profiles:
        for sf in stations:
            m_major = abs(sf.M3) * m_conv
            v_major = abs(sf.V2) * f_conv
            load_sets.append(
                LoadEffects(
                    Pu=-sf.P * f_conv,
                    Mu=m_major,
                    Mu2=m_major,
                    Mu3=abs(sf.M2) * m_conv,
                    Vu=v_major,
                    Vu2=v_major,
                    Vu3=abs(sf.V3) * f_conv,
                    Tu=abs(sf.T) * m_conv,
                )
            )
    return load_sets


def analysis_result_to_load_effects(
    element_id: Union[int, str],
    analysis_result: Optional[AnalysisResult],
    is_metric: bool = False,
    units: Optional[Any] = None,
) -> Optional[LoadEffects]:
    """
    Envelope a struct_core element result into one aci318 LoadEffects object (beam design).

    Moments, shears, and torsion are the largest magnitudes over all combinations and stations.
    Pu is the most tensile concurrent axial force, which is the conservative value for the
    axial terms of Vc (Table 22.5.5.1) and Tth (Table 22.7.4.1).
    """
    load_sets = analysis_result_to_load_sets(element_id, analysis_result, is_metric=is_metric, units=units)
    if load_sets is None:
        return None
    m_major = max(s.Mu2 for s in load_sets)
    v_major = max(s.Vu2 for s in load_sets)
    return LoadEffects(
        Pu=min(s.Pu for s in load_sets),
        Mu=m_major,
        Mu2=m_major,
        Mu3=max(s.Mu3 for s in load_sets),
        Vu=v_major,
        Vu2=v_major,
        Vu3=max(s.Vu3 for s in load_sets),
        Tu=max(s.Tu for s in load_sets),
    )


HANGER_BARS = (2, "#4")  # 2 #4 top hanger bars to support shear stirrup cage per standard CRSI / ACI 318 construction practice


def beam_result_to_core(
    element_id: Union[int, str],
    result: BeamDesignResult,
    elem_len_in: Optional[float] = None,
    b_in: Optional[float] = None,
    h_in: Optional[float] = None,
    cover_in: Optional[float] = None,
) -> Tuple[ElementDesignResult, ElementDetailingResult]:
    """Convert an aci318 beam result object into the struct_core schema representation. The bar positions use the
    cover of the section the beam was designed with, or ``cover_in`` for a result that carries no section."""
    elem_len_in = getattr(result, "_elem_len_in", elem_len_in)
    b_in = getattr(result, "_b_in", b_in)
    h_in = getattr(result, "_h_in", h_in)
    if elem_len_in is None or b_in is None or h_in is None:
        raise ValueError(f"Beam {element_id!r}: missing section dimensions (elem_len_in, b_in, h_in)")

    # Design-mode results carry the capacity checks of the selected layout: flexure DCR = Mu / phi*Mn,
    # shear DCR = Vu / phi*Vn (designed stirrups, or the Vs,max section limit when stirrups cannot suffice).
    flexure = result.flexure
    shear = result.shear

    as_req = max(0.0, float(result.required_flexure_As))
    as_prov = max(0.0, float(result.provided_flexure_As))
    dcr_flex = float(flexure.demand_capacity_ratio) if flexure is not None else 0.0
    phi_mn_val = _positive_or_none(flexure.phi_mn) if flexure is not None else None

    vu_val = abs(float(getattr(result, "Vu", 0.0) or 0.0))
    if shear is not None:
        phi_vn_val = float(shear.phi_vn)
        vn_total = float(shear.vn_concrete) + float(shear.vn_steel)
        phi_ratio = phi_vn_val / vn_total if vn_total > 0.0 else 0.0
        phi_vc_val = phi_ratio * float(shear.vn_concrete)
        phi_vs_val = phi_ratio * float(shear.vn_steel)
        dcr_shear = float(shear.demand_capacity_ratio)
    else:
        phi_vn_val = phi_vc_val = phi_vs_val = 0.0
        dcr_shear = 0.0

    if flexure is not None and phi_mn_val is not None:
        flexure_res = FlexureDesignResult(
            required_steel_area=as_req,
            provided_steel_area=as_prov,
            phi_mn=phi_mn_val,
            mu=float(getattr(result, "Mu", 0.0) or 0.0),
            dcr=dcr_flex,
            neutral_axis_depth=float(flexure.neutral_axis),
            steel_strain=float(flexure.steel_strain),
            passed=bool(dcr_flex <= 1.0 and flexure.status != "Failed"),
            messages=list(flexure.messages if flexure.messages else result.messages),
        )
    else:
        flexure_res = None

    if shear is not None and phi_vn_val > 0.0:
        shear_res = ShearDesignResult(
            required_shear_steel=float(result.required_shear_spacing or 0.0),
            provided_shear_steel=0.0,
            phi_vc=phi_vc_val,
            phi_vs=phi_vs_val,
            phi_vn=phi_vn_val,
            vu=vu_val,
            dcr=dcr_shear,
            passed=bool(dcr_shear <= 1.0 and shear.status != "Failed"),
            messages=list(shear.messages),
        )
    else:
        shear_res = None

    code_checks: List[CodeCheckResult] = []
    ductility = getattr(result, "ductility_ratio", None)
    if ductility is not None and flexure is not None and flexure.steel_strain > 0.0:
        code_checks.append(
            CodeCheckResult(
                clause="ACI 318 §9.3.3.1",
                description="Beam ductility: tension-controlled section (net tensile strain)",
                demand=ductility * float(flexure.steel_strain),
                capacity=float(flexure.steel_strain),
                dcr=float(ductility),
                passed=bool(ductility <= 1.0),
            )
        )
    torsion = getattr(result, "torsion", None)
    if torsion is not None:
        torsion_dcr = float(torsion.demand_capacity_ratio)
        code_checks.append(
            CodeCheckResult(
                clause="ACI 318 §22.7",
                description="Beam torsion",
                demand=torsion_dcr * float(torsion.phi_tn) if torsion.phi_tn > 0.0 else 0.0,
                capacity=max(float(torsion.phi_tn), 1e-9),
                dcr=torsion_dcr,
                passed=bool(torsion_dcr <= 1.0 and torsion.status != "Failed"),
                messages=list(torsion.messages),
            )
        )

    dcr_candidates = [c.dcr for c in code_checks]
    if flexure_res is not None:
        dcr_candidates.append(float(flexure_res.dcr))
    if shear_res is not None:
        dcr_candidates.append(float(shear_res.dcr))
    governing_dcr = max(dcr_candidates) if dcr_candidates else 0.0

    passed = bool(
        flexure_res is not None
        and shear_res is not None
        and flexure_res.passed
        and shear_res.passed
        and all(c.passed for c in code_checks)
    )
    design_result = ElementDesignResult(
        element_id=element_id,
        member_type="beam",
        flexure=flexure_res,
        shear=shear_res,
        code_checks=code_checks,
        governing_dcr=governing_dcr,
        passed=passed,
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
        # Bar positions inside the clear cover and stirrups of the section the beam was designed with
        trial = result.trial_section
        materials = getattr(result, "_materials", None)
        if trial is not None:
            cover = trial.cover
        elif materials is not None:
            cover = materials.cover
        elif cover_in is not None:
            cover = cover_in
        else:
            raise ValueError(f"Beam {element_id!r}: the design result has no section, so its cover is unknown")
        stirrup_db = BAR_DATABASE[getattr(result, "stirrup_bar_size", "#3") or "#3"]["diameter"]
        bottom_depth = (trial.tension_steel[1] if trial is not None else 0.0) or h_in - cover - 1.0

        # 1. Bottom flexural bars
        bot_bars_obj = getattr(result.detailing, "bars", []) if hasattr(result, "detailing") else []
        bot_count = 0
        bot_sz = None
        if bot_bars_obj:
            bot_bp = bot_bars_obj[0]
            bot_count = int(getattr(bot_bp, "count", 0))
            bot_sz = _parse_bar_size_num(getattr(bot_bp, "bar_size", "#8"))
        elif getattr(result, "suggested_bars", None) and str(result.suggested_bars).lower() != "none":
            parts = str(result.suggested_bars).split()
            if len(parts) == 2:
                bot_count = int(parts[0])
                bot_sz = _parse_bar_size_num(parts[1])

        eid_str = str(element_id).strip()
        clean_eid = eid_str[1:] if eid_str.upper().startswith("B") else eid_str
        mark_bot = f"B{clean_eid}-B1"
        mark_top = f"B{clean_eid}-T1"
        mark_st = f"B{clean_eid}-S1"

        if bot_count > 0 and bot_sz is not None:
            bot_cut_len = round(elem_len_in, 1)
            bot_tot_len = round(bot_count * bot_cut_len, 1)
            bot_wt = round((bot_tot_len / 12.0) * _get_bar_unit_weight(bot_sz), 2)
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
                    depth=round(bottom_depth, 1),
                    bars=[Bar(mark=mark_bot, size=bot_sz, count=bot_count, length=bot_cut_len, weight=bot_wt)],
                )
            )
        else:
            design_result.passed = False

        # 2. Top hanger bars
        top_count, top_sz_str = HANGER_BARS
        top_sz = _parse_bar_size_num(top_sz_str)
        top_cut_len = round(elem_len_in, 1)
        top_tot_len = round(top_count * top_cut_len, 1)
        top_wt = round((top_tot_len / 12.0) * _get_bar_unit_weight(top_sz), 2)
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
                depth=round(cover + stirrup_db + BAR_DATABASE[top_sz_str]["diameter"] / 2.0, 1),
                bars=[Bar(mark=mark_top, size=top_sz, count=top_count, length=top_cut_len, weight=top_wt)],
            )
        )

        # 3. Transverse stirrups
        st_sz = _parse_bar_size_num(getattr(result, "stirrup_bar_size", "#3") or "#3")
        spacing = float(getattr(result, "required_shear_spacing", 8.0) or 8.0)
        legs = int(getattr(result, "stirrup_legs", 2) or 2)
        st_w = max(2.0, b_in - 2.0 * cover)
        st_h = max(2.0, h_in - 2.0 * cover)
        st_cut_len = round(2.0 * (st_w + st_h) + 6.0, 1)
        st_qty = max(2, int(elem_len_in / max(1.0, spacing)) + 1)
        st_tot_len = round(st_qty * st_cut_len, 1)
        st_wt = round((st_tot_len / 12.0) * _get_bar_unit_weight(st_sz), 2)
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
    elem_len_in: Optional[float] = None,
    b_in: Optional[float] = None,
    h_in: Optional[float] = None,
    cover_in: Optional[float] = None,
) -> Tuple[ElementDesignResult, ElementDetailingResult]:
    """Convert an aci318 column result object into the struct_core schema representation."""
    elem_len_in = getattr(result, "_elem_len_in", elem_len_in)
    b_in = getattr(result, "_b_in", b_in)
    h_in = getattr(result, "_h_in", h_in)
    if elem_len_in is None or b_in is None or h_in is None:
        raise ValueError(f"Column {element_id!r}: missing section dimensions (elem_len_in, b_in, h_in)")
    if cover_in is None:
        sec_obj = getattr(result, "_section", getattr(result, "section", None))
        mat_obj = getattr(result, "_materials", None)
        det_obj = getattr(result, "detailing", None)
        det_cover = None
        if det_obj is not None:
            det_cover = getattr(det_obj, "cover", None)
            if det_cover is None and getattr(det_obj, "bars", None):
                det_cover = getattr(det_obj.bars[0], "cover", None)
            if det_cover is None and getattr(det_obj, "stirrups", None):
                det_cover = getattr(det_obj.stirrups[0], "cover", None)
        cover_in = getattr(sec_obj, "cover", None) or getattr(mat_obj, "cover", None) or det_cover
    if cover_in is None:
        raise ValueError(f"Column {element_id!r}: missing clear cover (cover_in)")

    # Axial-flexural strength (axial_flexure: the P-M check of the designed longitudinal bars) and ties
    flexure, shear = result.axial_flexure, result.shear
    phi_mn_val = _positive_or_none(flexure.phi_mn) if flexure is not None else None
    if flexure is not None and phi_mn_val is not None:
        dcr_flex = float(flexure.demand_capacity_ratio)
        flexure_res = FlexureDesignResult(
            required_steel_area=max(0.0, float(flexure.required_steel)),
            provided_steel_area=max(0.0, float(flexure.provided_steel)),
            phi_mn=phi_mn_val,
            mu=abs(float(getattr(result, "Mu", 0.0) or 0.0)),
            dcr=dcr_flex,
            neutral_axis_depth=max(0.0, float(flexure.neutral_axis)),
            steel_strain=float(flexure.steel_strain),
            passed=bool(dcr_flex <= 1.0 and flexure.status != "Failed"),
            messages=list(flexure.messages),
        )
    else:
        flexure_res = None

    if shear is not None and float(shear.phi_vn) > 0.0:
        phi_vn_val = float(shear.phi_vn)
        vn_total = float(shear.vn_concrete) + float(shear.vn_steel)
        phi_ratio = phi_vn_val / vn_total if vn_total > 0.0 else 0.0
        dcr_shear = float(shear.demand_capacity_ratio)
        shear_res = ShearDesignResult(
            required_shear_steel=0.0,
            provided_shear_steel=0.0,
            phi_vc=phi_ratio * float(shear.vn_concrete),
            phi_vs=phi_ratio * float(shear.vn_steel),
            phi_vn=phi_vn_val,
            vu=abs(float(getattr(result, "_vu_max", 0.0) or 0.0)),
            dcr=dcr_shear,
            passed=bool(dcr_shear <= 1.0 and shear.status != "Failed"),
            messages=list(shear.messages),
        )
    else:
        shear_res = None

    dcr_candidates = []
    if flexure_res is not None:
        dcr_candidates.append(float(flexure_res.dcr))
    if shear_res is not None:
        dcr_candidates.append(float(shear_res.dcr))
    governing_dcr = max(dcr_candidates) if dcr_candidates else 0.0

    passed = bool(
        flexure_res is not None
        and shear_res is not None
        and flexure_res.passed
        and shear_res.passed
    )
    design_result = ElementDesignResult(
        element_id=element_id,
        member_type="column",
        flexure=flexure_res,
        shear=shear_res,
        governing_dcr=governing_dcr,
        passed=passed,
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
        col_count = 0
        col_sz = None
        if col_bars_obj:
            # One placement per bar layer (equal bars): the column carries all of them
            col_count = sum(int(bp.count) for bp in col_bars_obj)
            col_sz = _parse_bar_size_num(col_bars_obj[0].bar_size)
        elif getattr(result, "suggested_bars", None) and str(result.suggested_bars).lower() != "none":
            parts = str(result.suggested_bars).split()
            if len(parts) == 2:
                col_count = int(parts[0])
                col_sz = _parse_bar_size_num(parts[1])

        eid_str = str(element_id).strip()
        clean_eid = eid_str[1:] if eid_str.upper().startswith("C") else eid_str

        anchorage = getattr(result.detailing, "anchorage", None) if hasattr(result, "detailing") else None
        if col_count > 0 and col_sz is not None:
            col_cut_len = round(elem_len_in, 1)
            col_tot_len = round(col_count * col_cut_len, 1)
            col_wt = round((col_tot_len / 12.0) * _get_bar_unit_weight(col_sz), 2)
            mark_col = f"C{clean_eid}-V1"
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

            # Seismic transverse ties and lap splice per ACI 318 §18.7.4 & §18.7.5
            tie_sz = 3 if col_sz <= 10 else 4
            db_main = col_sz / 8.0  # Main bar diameter in inches

            # ACI 318 §18.7.5.1 Confinement length Lo
            lo = max(b_in, h_in, elem_len_in / 6.0, 18.0)
            lo = min(lo, elem_len_in * 0.35)

            # ACI 318 §18.7.5.3 Hoop spacing so in Lo
            so_max = min(b_in / 4.0, h_in / 4.0, 6.0 * db_main, 4.0)
            so = round(max(2.0, so_max), 1)

            # ACI 318 §18.7.5.5 Mid-height tie spacing s_mid outside Lo
            s_mid = round(min(6.0 * db_main, 6.0, b_in / 2.0, h_in / 2.0), 1)
            s_mid = max(so, s_mid)

            # ACI 318 §18.8.3 Transverse reinforcement through joint
            s_joint = round(min(so * 1.5, 6.0), 1)

            # ACI 318 §18.7.4.3 Tension lap splice (Class B) at mid-height
            l_splice = max(48.0 * db_main, 30.0)
            l_splice = min(l_splice, max(12.0, (elem_len_in - 2.0 * lo) * 0.85))
            y_splice = round(elem_len_in / 2.0 - l_splice / 2.0, 1)

            lo_val = round(lo, 1)
            mid_end = round(elem_len_in - lo_val, 1)

            # 4 discrete zones: Bottom Lo, Central mid, Top Lo, Joint
            h_joint = 16.0  # nominal joint zone height in inches
            ties_layout = [
                StirrupLayout(size=tie_sz, spacing=so, legs=2, start_zone=0.0, end_zone=lo_val, zone_type="Lo"),
                StirrupLayout(size=tie_sz, spacing=s_mid, legs=2, start_zone=lo_val, end_zone=mid_end, zone_type="mid"),
                StirrupLayout(size=tie_sz, spacing=so, legs=2, start_zone=mid_end, end_zone=round(elem_len_in, 1), zone_type="Lo"),
                StirrupLayout(size=tie_sz, spacing=s_joint, legs=2, start_zone=round(elem_len_in, 1), end_zone=round(elem_len_in + h_joint, 1), zone_type="joint"),
            ]

            tie_w = max(2.0, b_in - 2.0 * cover_in)
            tie_h = max(2.0, h_in - 2.0 * cover_in)
            tie_cut_len = round(2.0 * (tie_w + tie_h) + 6.0, 1)
            qty_lo = max(1, int(lo_val / max(1.0, so)) + 1)
            qty_mid = max(1, int((mid_end - lo_val) / max(1.0, s_mid)) + 1)
            qty_joint = max(1, int(h_joint / max(1.0, s_joint)) + 1)
            tie_qty = 2 * qty_lo + qty_mid + qty_joint
            tie_tot_len = round(tie_qty * tie_cut_len, 1)
            tie_wt = round((tie_tot_len / 12.0) * _get_bar_unit_weight(tie_sz), 2)
            mark_tie = f"C{clean_eid}-T1"
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

            if anchorage is None:
                anchorage = Anchorage(
                    ld=round(l_splice, 1),
                    splice=LapSplice(
                        splice_class="Class B",
                        splice_length=round(l_splice, 1),
                        location=y_splice,
                    ),
                )
        else:
            design_result.passed = False

        tot_col_wt = round(sum(it.weight for it in sched_items), 2)
        bar_schedule = BarSchedule(items=sched_items, total_weight=tot_col_wt)
        bar_layout = BarLayout(top_layers=[], bottom_layers=bottom_layers, stirrups=ties_layout)

    detailing_result = ElementDetailingResult(
        element_id=element_id,
        member_type="column",
        bar_layout=bar_layout,
        bar_schedule=bar_schedule,
        anchorage=anchorage,
    )

    return design_result, detailing_result


def isolated_footing_result_to_core(
    element_id: Union[int, str],
    result: IsolatedFootingDesignResult,
    cover_in: Optional[float] = None,
) -> Tuple[ElementDesignResult, ElementDetailingResult]:
    """Convert an aci318 isolated footing result object into the struct_core schema representation."""
    raw_l = getattr(result, "length", None)
    raw_w = getattr(result, "width", None)
    raw_t = getattr(result, "thickness", None)
    if raw_l is None or raw_w is None or raw_t is None:
        raise ValueError(f"Footing {element_id!r}: missing dimensions (length, width, thickness)")

    cov = getattr(result, "cover", None)
    if cov is None:
        cov = cover_in
    if cov is None:
        raise ValueError(f"Footing {element_id!r}: missing clear cover (cover_in)")

    L_disp = float(raw_l) * 12.0  # in
    W_disp = float(raw_w) * 12.0  # in
    T_disp = float(raw_t)        # in
    cov_in = float(cov)

    dcr_flex = max(result.flexure_x.demand_capacity_ratio, result.flexure_y.demand_capacity_ratio)
    dcr_shear = max(result.one_way_shear.demand_capacity_ratio, result.punching_shear.demand_capacity_ratio)
    dcr_bearing = (
        result.max_bearing_pressure / result.allowable_bearing_capacity
        if result.allowable_bearing_capacity > 0.0
        else 0.0
    )
    governing_dcr = max(dcr_flex, dcr_shear, dcr_bearing)

    req_as = max(float(getattr(result, "required_As_x", 0.0) or 0.0), float(getattr(result, "required_As_y", 0.0) or 0.0))
    prov_as = max(
        float(getattr(result.flexure_x, "provided_steel", 0.0) or 0.0),
        float(getattr(result.flexure_y, "provided_steel", 0.0) or 0.0),
        req_as,
    )
    phi_mn_val = float(getattr(result.flexure_x, "phi_mn", 1.0) or 1.0)
    mu_val = round(phi_mn_val * float(getattr(result.flexure_x, "demand_capacity_ratio", 0.0) or 0.0), 3)

    flexure_res = FlexureDesignResult(
        required_steel_area=req_as,
        provided_steel_area=prov_as,
        phi_mn=phi_mn_val,
        mu=mu_val,
        dcr=dcr_flex,
        passed=bool(result.status != "Failed"),
        messages=list(result.messages or []),
    )
    phi_vn_val = float(getattr(result.punching_shear, "phi_vn", 1.0) or 1.0)
    vu_val = round(phi_vn_val * float(getattr(result.punching_shear, "demand_capacity_ratio", 0.0) or 0.0), 3)
    shear_res = ShearDesignResult(
        required_shear_steel=0.0,
        provided_shear_steel=0.0,
        phi_vc=phi_vn_val,
        phi_vs=0.0,
        phi_vn=phi_vn_val,
        vu=vu_val,
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
        passed=bool(result.status != "Failed" and governing_dcr <= 1.0),
    )

    items: List[BarScheduleItem] = []
    bars_list: List[Bar] = []
    tot_wt = 0.0

    if hasattr(result, "detailing") and getattr(result.detailing, "bars", None):
        for bp in result.detailing.bars:
            sz_num = _parse_bar_size_num(bp.bar_size)
            qty = int(bp.count)
            is_y = "y" in str(bp.location).lower()
            span_dim = W_disp if is_y else L_disp
            cut_len = round(max(12.0, span_dim - 2.0 * cov_in), 1)
            tot_len = round(qty * cut_len, 1)
            unit_wt = _get_bar_unit_weight(sz_num) / 12.0
            wt = round(tot_len * unit_wt, 2)
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
        bottom_layers=[RebarLayer(depth=round(max(1.0, T_disp - cov_in), 1), bars=bars_list)],
    )
    bar_schedule = BarSchedule(items=items, total_weight=round(tot_wt, 2))

    detailing_res = ElementDetailingResult(
        element_id=element_id,
        member_type="footing",
        bar_layout=bar_layout,
        bar_schedule=bar_schedule,
    )
    object.__setattr__(detailing_res, "_length_in", L_disp)
    object.__setattr__(detailing_res, "_width_in", W_disp)
    object.__setattr__(detailing_res, "_thickness_in", T_disp)
    object.__setattr__(detailing_res, "_cover_in", cov_in)
    object.__setattr__(design_res, "_length_in", L_disp)
    object.__setattr__(design_res, "_width_in", W_disp)
    object.__setattr__(design_res, "_thickness_in", T_disp)
    object.__setattr__(design_res, "_cover_in", cov_in)
    return design_res, detailing_res


def design_from_core(
    model_or_project: Union[StructuralModel, Project],
    analysis_result: Optional[AnalysisResult] = None,
    design_code: str = "ACI 318-25",
    design_result: Optional[Any] = None,
    detailing_result: Optional[Any] = None,
    *,
    allowable_bearing_pressure: Optional[float] = None,
    footing_cover: Optional[float] = None,
    service_analysis_results: Optional[Sequence[AnalysisResult]] = None,
) -> Tuple[CoreDesignResult, CoreDetailingResult]:
    """
    Convert existing engineering results into struct_core result schemas.

    If ``design_result`` is omitted, the adapter will orchestrate the aci318
    member design APIs (``Beam.design`` / column reinforcement design) using the supplied
    analysis result and struct_core sections/materials, then convert the
    outputs. Conversion is the only logic performed directly by the adapter.

    Every designed section must name its concrete, longitudinal and transverse rebar materials and clear cover
    (``ValueError`` otherwise). Isolated footings are designed under the supported columns only when
    ``allowable_bearing_pressure`` (model pressure unit), ``footing_cover`` (model length unit) and
    ``service_analysis_results`` (one result per service-level load combination, for the bearing check) are all
    given. The design result records its inputs (``DesignResult.inputs``).
    """
    model, analysis_result = _unwrap_model(model_or_project, analysis_result)

    units = (
        getattr(getattr(model_or_project, "metadata", None), "units", None)
        or getattr(getattr(model, "metadata", None), "units", None)
        or getattr(model_or_project, "units", None)
        or getattr(model, "units", None)
    )
    if units is None:
        raise ValueError("Units are required for ACI 318 design. Provide a Project or model with units.")
    design_footings = None not in (allowable_bearing_pressure, footing_cover, service_analysis_results)

    basis = getattr(model_or_project, "seismic_basis", None)
    system = _FRAME_SYSTEMS.get(getattr(basis, "system", None), "none")
    sds = float(basis.sds) if basis is not None and basis.sds is not None else 0.0

    if design_result is None:
        if analysis_result is not None and model.elements:
            design_result = _run_member_design(
                model, analysis_result, units=units, design_code=design_code, frame_system=system
            )
            if system == "smf":
                _proportion_columns_for_strong_column(
                    model, design_result, analysis_result, units, _code_for(design_code), sds
                )
            if design_footings:
                design_result.update(_design_footings(
                    model, analysis_result, service_analysis_results, allowable_bearing_pressure, footing_cover,
                    units, _code_for(design_code),
                ))
        elif isinstance(model_or_project, Project):
            design_result = model_or_project.design_result

    if detailing_result is None:
        if isinstance(design_result, Mapping) and design_result:
            detailing_result = design_result
        elif isinstance(model_or_project, Project):
            detailing_result = model_or_project.detailing_result

    if design_result is None and detailing_result is None:
        raise ValueError(
            "No precomputed aci318 design/detailing result was supplied and no "
            "analysis result is available to run member design. Provide one of "
            "the following: design_result, analysis_result, or a Project with an "
            "attached analysis_results entry."
        )

    core_detailing = CoreDetailingResult(
        units=parse_units("lbf, in"),
        bar_system="US",
        element_results={},
        aggregate_schedule=None,
    )
    if isinstance(detailing_result, CoreDetailingResult):
        core_detailing = detailing_result
        if core_detailing.units is None:
            core_detailing.units = parse_units("lbf, in")
        if not getattr(core_detailing, "bar_system", None):
            core_detailing.bar_system = "US"

    # If the caller already passed real struct_core schema objects, return them directly.
    if isinstance(design_result, CoreDesignResult):
        core_design = design_result
        if core_design.units is None:
            core_design.units = parse_units("kip, in")
    else:
        core_design = CoreDesignResult(
            units=parse_units("kip, in"),
            design_code=design_code,
            element_results={},
            governing_dcr=0.0,
            passed=True,
        )

        def _get_dims(elem_id_val, is_col=False):
            elem = next((e for e in model.elements if str(e.id) == str(elem_id_val)), None)
            if elem is None:
                raise ValueError(f"Element {elem_id_val!r} not found in model")
            sec = model.section_of(elem.id)
            if sec is None:
                raise ValueError(f"Element {elem_id_val!r} has no section")
            b_m, h_m, dia_m, is_circ = _section_dimensions(sec, units=units)
            b_val = dia_m if is_circ else b_m
            h_val = dia_m if is_circ else h_m
            start_n = next((n for n in model.nodes if str(n.id) == str(elem.start_node)), None)
            end_n = next((n for n in model.nodes if str(n.id) == str(elem.end_node)), None)
            if start_n is None or end_n is None:
                raise ValueError(f"Element {elem_id_val!r} missing nodes")
            dx = float(end_n.x) - float(start_n.x)
            dy = float(end_n.y) - float(start_n.y)
            dz = float(end_n.z) - float(start_n.z)
            raw_l = (dx**2 + dy**2 + dz**2)**0.5
            len_scale = conversion_factor(units, PRESETS["kip, in, s, °F"], "length")
            return raw_l * len_scale, b_val, h_val

        if isinstance(design_result, Mapping):
            for elem_id, member_result in design_result.items():
                if isinstance(member_result, BeamDesignResult):
                    elem_len = getattr(member_result, "_elem_len_in", None)
                    b_in = getattr(member_result, "_b_in", None)
                    h_in = getattr(member_result, "_h_in", None)
                    if elem_len is None or b_in is None or h_in is None:
                        m_len, m_b, m_h = _get_dims(elem_id)
                        elem_len = elem_len if elem_len is not None else m_len
                        b_in = b_in if b_in is not None else m_b
                        h_in = h_in if h_in is not None else m_h
                    elem_design, elem_detailing = beam_result_to_core(
                        elem_id, member_result, elem_len_in=elem_len, b_in=b_in, h_in=h_in,
                        cover_in=_model_cover_in(model, elem_id, units),
                    )
                    core_design.element_results[elem_id] = elem_design
                    if elem_id not in core_detailing.element_results:
                        core_detailing.element_results[elem_id] = elem_detailing
                elif isinstance(member_result, ColumnDesignResult):
                    elem_len = getattr(member_result, "_elem_len_in", None)
                    b_in = getattr(member_result, "_b_in", None)
                    h_in = getattr(member_result, "_h_in", None)
                    if elem_len is None or b_in is None or h_in is None:
                        m_len, m_b, m_h = _get_dims(elem_id, is_col=True)
                        elem_len = elem_len if elem_len is not None else m_len
                        b_in = b_in if b_in is not None else m_b
                        h_in = h_in if h_in is not None else m_h
                    elem_design, elem_detailing = column_result_to_core(
                        elem_id, member_result, elem_len_in=elem_len, b_in=b_in, h_in=h_in,
                        cover_in=_model_cover_in(model, elem_id, units),
                    )
                    core_design.element_results[elem_id] = elem_design
                    if elem_id not in core_detailing.element_results:
                        core_detailing.element_results[elem_id] = elem_detailing
                elif isinstance(member_result, IsolatedFootingDesignResult):
                    ftg_cov_in = (
                        footing_cover * conversion_factor(units, _KIP_IN, "length")
                        if footing_cover is not None
                        else getattr(member_result, "cover", 3.0)
                    )
                    elem_design, elem_detailing = isolated_footing_result_to_core(
                        elem_id, member_result, cover_in=ftg_cov_in
                    )
                    core_design.element_results[elem_id] = elem_design
                    if elem_id not in core_detailing.element_results:
                        core_detailing.element_results[elem_id] = elem_detailing
                elif isinstance(member_result, ElementDesignResult):
                    core_design.element_results[elem_id] = member_result

        elif isinstance(design_result, BeamDesignResult):
            elem_id = next(iter(model.elements)).id
            elem_len = getattr(design_result, "_elem_len_in", None)
            b_in = getattr(design_result, "_b_in", None)
            h_in = getattr(design_result, "_h_in", None)
            if elem_len is None or b_in is None or h_in is None:
                m_len, m_b, m_h = _get_dims(elem_id)
                elem_len = elem_len if elem_len is not None else m_len
                b_in = b_in if b_in is not None else m_b
                h_in = h_in if h_in is not None else m_h
            elem_design, elem_detailing = beam_result_to_core(
                elem_id, design_result, elem_len_in=elem_len, b_in=b_in, h_in=h_in,
                cover_in=_model_cover_in(model, elem_id, units),
            )
            core_design.element_results[elem_id] = elem_design
            core_detailing.element_results[elem_id] = elem_detailing
        elif isinstance(design_result, ColumnDesignResult):
            elem_id = next(iter(model.elements)).id
            elem_len = getattr(design_result, "_elem_len_in", None)
            b_in = getattr(design_result, "_b_in", None)
            h_in = getattr(design_result, "_h_in", None)
            if elem_len is None or b_in is None or h_in is None:
                m_len, m_b, m_h = _get_dims(elem_id, is_col=True)
                elem_len = elem_len if elem_len is not None else m_len
                b_in = b_in if b_in is not None else m_b
                h_in = h_in if h_in is not None else m_h
            elem_design, elem_detailing = column_result_to_core(
                elem_id, design_result, elem_len_in=elem_len, b_in=b_in, h_in=h_in,
                cover_in=_model_cover_in(model, elem_id, units),
            )
            core_design.element_results[elem_id] = elem_design
            core_detailing.element_results[elem_id] = elem_detailing
        elif isinstance(design_result, IsolatedFootingDesignResult):
            elem_id = next(iter(model.elements)).id
            elem_design, elem_detailing = isolated_footing_result_to_core(
                elem_id, design_result, cover_in=footing_cover
            )
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

    # Frame-level checks: joints (Chapter 15 / 18), Chapter 18 members, and the analysis checks
    # (slenderness, story drift, stability) carried by the analysis result
    if isinstance(design_result, Mapping) and analysis_result is not None and model.elements:
        code = _code_for(design_code)
        per_element, joint_checks = _frame_level_checks(
            model, design_result, analysis_result, units, code, system, sds
        )
        for elem_id, extra in per_element.items():
            edr = core_design.element_results.get(elem_id)
            if edr is None or not extra:
                continue
            edr.code_checks.extend(extra)
            edr.governing_dcr = max([edr.governing_dcr] + [c.dcr for c in extra])
            edr.passed = bool(edr.passed and all(c.passed for c in extra))
        core_design.system_checks = list(analysis_result.code_checks) + joint_checks

    if core_design.element_results:
        core_design.governing_dcr = max(
            [float(getattr(item, "governing_dcr", 0.0)) for item in core_design.element_results.values()]
            + [c.dcr for c in core_design.system_checks],
            default=0.0,
        )
        core_design.passed = all(bool(getattr(item, "passed", True)) for item in core_design.element_results.values()) \
            and all(c.passed for c in core_design.system_checks)

    if analysis_result is not None and isinstance(design_result, Mapping) and design_result:
        core_design.inputs = _design_inputs(
            model, design_code, allowable_bearing_pressure if design_footings else None,
            footing_cover if design_footings else None,
        )

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


# ASCE 7 seismic system key -> ACI 318 Chapter 18 frame type
_FRAME_SYSTEMS = {"rc_smf": "smf", "rc_imf": "imf", "rc_omf": "omf"}


def _code_for(design_code: str):
    if "25" in str(design_code):
        from aci318.codes.aci318_25 import ACI318_25
        return ACI318_25()
    return ACI318_19()


def _beam_joint_moments(
    element: Any,
    start: Any,
    end: Any,
    elem_res: Optional[ElementResult],
    axis: str,
    direction: str,
    m_conv: float,
) -> Dict[Any, Dict[str, float]]:
    """
    Moment a horizontal beam applies to each end node per load combination, signed about the
    global horizontal axis normal to its frame plane (global z for a planar x-y frame; global Y
    for 'x' beams and global X for 'y' beams when z is vertical).

    The station moments are internal forces in the element local axes (struct_core convention,
    first station at the start node): the node receives +M at the start and -M at the end. The
    local axes follow the solver default orientation: local 3 is out of plane for a planar frame;
    otherwise local 3 = (v1y, -v1x, 0)/|.|, local 2 = local 3 x local 1, rotated by the roll angle.
    """
    if elem_res is None:
        return {}
    profiles = dict(elem_res.combination_forces) or ({"case": elem_res.forces} if elem_res.forces else {})
    if axis == "y":
        w2, w3 = 0.0, 1.0
    else:
        v1 = [float(getattr(end, c, 0.0)) - float(getattr(start, c, 0.0)) for c in ("x", "y", "z")]
        length = math.sqrt(sum(c * c for c in v1))
        v1 = [c / length for c in v1]
        proj = math.hypot(v1[0], v1[1])
        v3 = [v1[1] / proj, -v1[0] / proj, 0.0]
        v2 = [v3[1] * v1[2] - v3[2] * v1[1], v3[2] * v1[0] - v3[0] * v1[2], v3[0] * v1[1] - v3[1] * v1[0]]
        beta = math.radians(float(getattr(element, "roll_angle", 0.0) or 0.0))
        v2, v3 = (
            [math.cos(beta) * a + math.sin(beta) * b for a, b in zip(v2, v3)],
            [-math.sin(beta) * a + math.cos(beta) * b for a, b in zip(v2, v3)],
        )
        k = 1 if direction == "x" else 0
        w2, w3 = v2[k], v3[k]
    moments: Dict[Any, Dict[str, float]] = {element.start_node: {}, element.end_node: {}}
    for combo, stations in profiles.items():
        if not stations:
            continue
        first, last = stations[0], stations[-1]
        moments[element.start_node][str(combo)] = (first.M2 * w2 + first.M3 * w3) * m_conv
        moments[element.end_node][str(combo)] = -(last.M2 * w2 + last.M3 * w3) * m_conv
    return moments


@dataclass
class _FrameModel:
    """Beams, columns, and joints of a designed frame, as the Chapter 15 / 18 provisions see them."""

    beams: Dict[str, Any]          # FrameBeam by element id (str)
    beam_ids: Dict[str, Any]       # element id (str) -> model element id, beams with a framing direction
    columns: Dict[str, Any]        # FrameColumn by element id (str); rectangular columns only
    column_ids: Dict[str, Any]     # element id (str) -> model element id
    joints: List[Any]              # FrameJoint


def _assemble_frame(
    model: StructuralModel,
    member_results: Mapping[Any, Any],
    analysis_result: AnalysisResult,
    units: Optional[Any],
    sds: float,
) -> _FrameModel:
    """Frame beams, columns, and joints from the member design results (all in kip and inches)."""
    from struct_core import classify_frame_members, node_elevation, vertical_axis

    from aci318.seismic import FrameBeam, FrameColumn, FrameJoint

    if units is None:
        raise ValueError("Units are required for seismic frame design. Pass units= or set model.units.")
    to_in = conversion_factor(units, PRESETS["kip, in, s, °F"], "length")
    f_conv = conversion_factor(units, PRESETS["kip, in, s, °F"], "force")
    m_conv = conversion_factor(units, PRESETS["kip, in, s, °F"], "moment")
    roles = classify_frame_members(model)
    axis = vertical_axis(model)
    nodes = {n.id: n for n in model.nodes}
    elements = {e.id: e for e in model.elements}

    def ends(eid):
        el = elements[eid]
        zi, zj = node_elevation(model, nodes[el.start_node]), node_elevation(model, nodes[el.end_node])
        return (el.start_node, el.end_node) if zi <= zj else (el.end_node, el.start_node)

    def length_in(eid):
        el = elements[eid]
        a, b = nodes[el.start_node], nodes[el.end_node]
        return math.dist((a.x, a.y, getattr(a, "z", 0.0)), (b.x, b.y, getattr(b, "z", 0.0))) * to_in

    columns_at: Dict[Any, List[Any]] = {}
    for eid, role in roles.items():
        if role == "column" and isinstance(member_results.get(eid), ColumnDesignResult):
            for nid in ends(eid):
                columns_at.setdefault(nid, []).append(eid)

    # Factored gravity load along each beam for the capacity-design shears: (1.2 + 0.2 SDS) D + 1.0 L
    dead = [lc for lc in model.load_cases if any(t in str(lc.id).lower() for t in ("dead", "sdl"))]
    live = [lc for lc in model.load_cases if "live" in str(lc.id).lower() and "roof" not in str(lc.id).lower()]
    w_vertical: Dict[Any, float] = {}
    for factor, cases in ((1.2 + 0.2 * sds, dead), (1.0, live)):
        for lc in cases:
            for dl in lc.element_loads:
                w = abs(dl.w2) if dl.is_local else abs(getattr(dl, f"w{axis}"))
                w_vertical[dl.element_id] = w_vertical.get(dl.element_id, 0.0) + factor * w * f_conv / to_in

    beams: Dict[str, FrameBeam] = {}
    beam_dirs: Dict[Any, str] = {}
    for eid, role in roles.items():
        res = member_results.get(eid)
        if role != "beam" or not isinstance(res, BeamDesignResult) or res.suggested_bars in (None, "None"):
            continue
        n_bars, size = str(res.suggested_bars).split()
        el = elements[eid]
        a, b = nodes[el.start_node], nodes[el.end_node]
        direction = "x" if axis == "y" or abs(b.x - a.x) >= abs(b.y - a.y) else "y"
        col_dims = [
            max(getattr(member_results[c], "_b_in"), getattr(member_results[c], "_h_in"))
            for nid in (el.start_node, el.end_node) for c in columns_at.get(nid, [])[:1]
        ]
        clear = length_in(eid) - 0.5 * sum(col_dims)
        joint_moments = _beam_joint_moments(
            el, a, b, _find_element_result(eid, analysis_result), axis, direction, m_conv
        )
        beams[str(eid)] = FrameBeam(
            id=str(eid), b=res._b_in, h=res._h_in, d=res.trial_section.tension_steel[1],
            clear_span=clear, n_bars=int(n_bars), bar_size=size, concrete=res._concrete,
            wu=w_vertical.get(eid, 0.0), direction=direction,
            fy=res._materials.steel.fy, fyt=res._materials.fyt, cover=res._materials.cover,
            end_moments={str(nid): m for nid, m in joint_moments.items() if m},
        )
        beam_dirs[eid] = direction

    beam_depth_at: Dict[Any, float] = {}
    for eid in beam_dirs:
        for nid in (elements[eid].start_node, elements[eid].end_node):
            beam_depth_at[nid] = max(beam_depth_at.get(nid, 0.0), beams[str(eid)].h)

    columns: Dict[str, FrameColumn] = {}
    for nid_cols in columns_at.values():
        for eid in nid_cols:
            if str(eid) in columns:
                continue
            res = member_results[eid]
            sec = res._section
            if getattr(sec, "bar_pattern", None) is None:
                continue  # circular columns: frame checks not implemented
            n_b, n_h, size = sec.bar_pattern[:3]
            top = ends(eid)[1]
            columns[str(eid)] = FrameColumn(
                id=str(eid), section=sec, clear_height=length_in(eid) - beam_depth_at.get(top, 0.0),
                pu_values=res._pu_values, vu_analysis=res._vu_max, bars_per_face=(n_b, n_h), bar_size=size,
                fyt=res._materials.fyt,
            )

    joints: List[FrameJoint] = []
    for nid, cols in columns_at.items():
        framing: Dict[str, List[str]] = {}
        for eid, d in beam_dirs.items():
            if nid in (elements[eid].start_node, elements[eid].end_node):
                framing.setdefault(d, []).append(str(eid))
        if not framing:
            continue
        below = next((c for c in cols if ends(c)[1] == nid), None)
        above = next((c for c in cols if ends(c)[0] == nid), None)
        joints.append(FrameJoint(
            id=str(nid), beams=framing,
            column_below=str(below) if below is not None and str(below) in columns else None,
            column_above=str(above) if above is not None and str(above) in columns else None,
            height_below=length_in(below) if below is not None else 0.0,
            height_above=length_in(above) if above is not None else 0.0,
        ))

    return _FrameModel(
        beams=beams, beam_ids={str(eid): eid for eid in beam_dirs},
        columns=columns, column_ids={str(eid): eid for eid in roles if str(eid) in columns}, joints=joints,
    )


def _frame_level_checks(
    model: StructuralModel,
    member_results: Mapping[Any, Any],
    analysis_result: AnalysisResult,
    units: Optional[Any],
    code: Any,
    system: str,
    sds: float,
) -> Tuple[Dict[Any, List[CodeCheckResult]], List[CodeCheckResult]]:
    """
    Joint shear for every frame (ACI 318-25 Chapter 15, or 18.3.4 / 18.4.4.7 / 18.8.4) and the
    Chapter 18 beam, column, and strong-column/weak-beam checks of the seismic frame type.

    Returns (code checks per element, joint checks).
    """
    from aci318.seismic import beam_end_moment_limits, check_beam, check_column, check_joint

    frame = _assemble_frame(model, member_results, analysis_result, units, sds)

    def to_core(check) -> CodeCheckResult:
        return CodeCheckResult(
            clause=check.clause, description=check.description, demand=float(check.demand),
            capacity=max(float(check.capacity), 1e-9), dcr=float(check.dcr) if math.isfinite(check.dcr) else 1e9,
            passed=check.passed, messages=list(check.messages),
        )

    per_element: Dict[Any, List[CodeCheckResult]] = {}
    for key, eid in frame.beam_ids.items():
        per_element[eid] = [to_core(c) for c in check_beam(frame.beams[key], code, system, sds)]
    for key, col in frame.columns.items():
        limits = beam_end_moment_limits(key, frame.joints, frame.beams, code) if system == "smf" else (None, None)
        per_element[frame.column_ids[key]] = [to_core(c) for c in check_column(col, code, system, limits)]
    joint_checks = [to_core(c) for j in frame.joints for c in check_joint(j, frame.beams, frame.columns, code, system)]
    return per_element, joint_checks


def _proportion_columns_for_strong_column(
    model: StructuralModel,
    member_results: Dict[Any, Any],
    analysis_result: AnalysisResult,
    units: Optional[Any],
    code: Any,
    sds: float,
) -> None:
    """
    Special moment frames: raise column bars where strong-column/weak-beam (18.7.3.2) fails
    (``aci318.seismic.strong_column``), and re-check every raised column for its load sets.
    """
    from aci318.members.column_reinforcement import candidate_layouts, check_layout
    from aci318.seismic import proportion_for_strong_column

    frame = _assemble_frame(model, member_results, analysis_result, units, sds)
    max_ratio = max_longitudinal_ratio("smf")
    layouts = {
        key: candidate_layouts(col.section, max_ratio, max_spacing=max_supported_bar_spacing(
            "smf", max(col.pu_values), col.section.gross_area, col.section.concrete.fc))
        for key, col in frame.columns.items()
    }
    raised = proportion_for_strong_column(frame.joints, frame.beams, frame.columns, code, layouts)
    for key, layout in raised.items():
        eid = frame.column_ids[key]
        old = member_results[eid]
        result = check_layout(old._section, layout, old._load_sets, code, old._materials.steel, member_id=str(eid),
                              fy_shear=old._materials.fyt)
        member_results[eid] = _annotate_column_result(
            result, old._section, old._load_sets, old._materials, elem_len_in=old._elem_len_in, b_in=old._b_in,
            h_in=old._h_in, mu=old.Mu, vu=old.Vu,
        )


def _annotate_column_result(
    result: ColumnDesignResult,
    section: Any,
    load_sets: Sequence[LoadEffects],
    materials: _SectionMaterials,
    *,
    elem_len_in: float,
    b_in: float,
    h_in: float,
    mu: float,
    vu: float,
) -> ColumnDesignResult:
    """Attach to a column result what the frame checks, the core conversion, and a re-check read."""
    result._section = section
    result._materials = materials
    result._load_sets = list(load_sets)
    result._pu_values = [s.Pu for s in load_sets]
    result._vu_max = max(max(s.Vu2, s.Vu3) for s in load_sets)
    result._elem_len_in = elem_len_in
    result._b_in = b_in
    result._h_in = h_in
    result.Mu = mu
    result.Vu = vu
    return result


def _run_member_design(
    model: StructuralModel,
    analysis_result: AnalysisResult,
    units: Optional[Any] = None,
    design_code: str = "ACI 318-25",
    frame_system: str = "none",
) -> Dict[Union[int, str], Any]:
    """
    Run aci318 Beam / Column design for each element using the supplied analysis result.

    Column longitudinal bars are designed for strength within the steel limits of ``frame_system``
    (Chapter 18 frame type: 'smf', 'imf', 'omf', or 'none'); see ``aci318.members.column_reinforcement``.
    """
    from struct_core import classify_frame_members

    if units is None:
        units = getattr(model, "units", None)
    if units is None:
        raise ValueError("Units are required for ACI 318 design. Pass units= or set model.units.")
    sections_by_id = {getattr(s, "id", None): s for s in model.sections}
    nodes_by_id = {getattr(n, "id", None): n for n in model.nodes}
    section_materials = designed_section_materials(model, units)  # one error lists every incomplete section
    roles = classify_frame_members(model)
    code = _code_for(design_code)

    is_metric_model = False
    if units is not None:
        u_len = str(getattr(units, "length", "")).lower()
        is_metric_model = u_len in ("m", "mm", "cm") or bool(getattr(units, "is_metric", False))

    member_results: Dict[Union[int, str], Any] = {}
    for element in model.elements:
        elem_id = getattr(element, "id", None)
        sec_schema = sections_by_id.get(getattr(element, "section_id", None))
        if sec_schema is None:
            raise ValueError(f"Element {elem_id} references missing section '{getattr(element, 'section_id', None)}'.")

        materials = section_materials[sec_schema.id]
        concrete = materials.concrete

        loads = analysis_result_to_load_effects(elem_id, analysis_result, is_metric=is_metric_model, units=units) or LoadEffects()

        b, h, dia, is_circular = _section_dimensions(sec_schema, units=units)
        is_column = roles.get(elem_id) in ("column", "brace")

        # Calculate element length in inches
        start_node = nodes_by_id.get(getattr(element, "start_node", None))
        end_node = nodes_by_id.get(getattr(element, "end_node", None))
        if start_node is None or end_node is None:
            raise ValueError(f"Element {elem_id} references missing start_node ({getattr(element, 'start_node', None)}) or end_node ({getattr(element, 'end_node', None)}).")

        dx = float(getattr(end_node, "x", 0.0)) - float(getattr(start_node, "x", 0.0))
        dy = float(getattr(end_node, "y", 0.0)) - float(getattr(start_node, "y", 0.0))
        dz = float(getattr(end_node, "z", 0.0)) - float(getattr(start_node, "z", 0.0))
        raw_len = (dx**2 + dy**2 + dz**2)**0.5
        len_scale = conversion_factor(units, PRESETS["kip, in, s, °F"], "length")
        elem_len_in = raw_len * len_scale

        if is_column:
            section = CircularSection(D=dia, concrete=concrete, cover=materials.cover) if is_circular else RectangleSection(
                b=b, h=h, concrete=concrete, cover=materials.cover
            )
            load_sets = analysis_result_to_load_sets(
                elem_id, analysis_result, is_metric=is_metric_model, units=units
            ) or [LoadEffects()]
            max_spacing = max_supported_bar_spacing(
                frame_system, max(s.Pu for s in load_sets), section.gross_area, concrete.fc
            )
            col_res = design_longitudinal_reinforcement(
                section, load_sets, code, steel=materials.steel, max_ratio=max_longitudinal_ratio(frame_system),
                member_id=str(elem_id), max_spacing=max_spacing, fy_shear=materials.fyt,
            ).result
            col_res = _annotate_column_result(
                col_res, section, load_sets, materials, elem_len_in=elem_len_in,
                b_in=dia if is_circular else b, h_in=dia if is_circular else h, mu=loads.Mu, vu=loads.Vu,
            )
            member_results[elem_id] = col_res
        else:
            section = RectangleSection(b=b, h=h, concrete=concrete, cover=materials.cover)
            beam = Beam(section=section, code=code, member_id=str(elem_id), fy_shear=materials.fyt)
            beam_res = beam.design(loads, fy_flexure=materials.steel.fy)
            setattr(beam_res, "_concrete", concrete)
            setattr(beam_res, "_materials", materials)
            setattr(beam_res, "_elem_len_in", elem_len_in)
            setattr(beam_res, "_b_in", b)
            setattr(beam_res, "_h_in", h)
            setattr(beam_res, "Mu", loads.Mu)
            setattr(beam_res, "Vu", loads.Vu)
            member_results[elem_id] = beam_res

    return member_results


def _design_inputs(
    model: StructuralModel, design_code: str, allowable_bearing_pressure: Optional[float], footing_cover: Optional[float]
) -> DesignInputs:
    """Copies of the sections designed and of their materials (as used), and the foundation inputs; model units."""
    from struct_core.design_result.design_inputs import AppliedDefault
    section_ids = {e.section_id for e in model.elements if e.type in ("beam", "truss")}
    sections = [s.model_copy(deep=True) for s in model.sections if s.id in section_ids]
    material_ids = set()
    for sec in sections:
        material_ids.update(m for m in (sec.material_id, getattr(sec, "rebar_material_id", None),
                                        getattr(sec, "transverse_rebar_material_id", None)) if m is not None)
    materials = [m.model_copy(deep=True) for m in model.materials if m.id in material_ids]
    defaults_applied = [
        AppliedDefault(
            name="hanger_bars",
            value=f"{HANGER_BARS[0]} {HANGER_BARS[1]}",
            unit=None,
            source="standard CRSI / ACI 318 construction practice for shear stirrup cage support",
        )
    ]
    return DesignInputs(
        design_code=design_code,
        materials=materials,
        sections=sections,
        allowable_bearing_pressure=allowable_bearing_pressure,
        footing_cover=footing_cover,
        defaults_applied=defaults_applied,
    )


def _model_cover_in(model: StructuralModel, element_id: Any, units: Any) -> Optional[float]:
    """Clear cover (in) of an element's section in the model, or None when it has none."""
    if units is None:
        units = getattr(model, "units", None)
    if units is None:
        raise ValueError("Units unknown: pass units= or use a Project")
    section = model.section_of(element_id)
    cover = getattr(section, "cover", None)
    return None if cover is None else cover * conversion_factor(units, _KIP_IN, "length")


def _support_reactions(result: Optional[AnalysisResult], node_id: Any) -> List[Any]:
    node_results = getattr(result, "node_results", None) or {}
    nr = node_results.get(node_id)
    if nr is None:
        nr = node_results.get(str(node_id))
    if nr is None:
        return []
    combo_rxns = getattr(nr, "combination_reactions", None) or {}
    if combo_rxns:
        return [r for r in combo_rxns.values() if r is not None]
    rxn = getattr(nr, "reaction", None)
    return [rxn] if rxn is not None else []


def _footing_load(reaction: Any, is_3d: bool, f_conv: float, m_conv: float) -> LoadEffects:
    """Column load on a footing from a support reaction: signed P (kip, compression positive, uplift negative),
    biaxial moments (kip-in: My bends in X-Z along L -> Mu2, Mx bends in Y-Z along B -> Mu3) and horizontal shear (kip)."""
    if is_3d:
        vertical = float(reaction.fz)
        horizontal = max(abs(float(reaction.fx)), abs(float(reaction.fy)))
        mx = abs(float(reaction.mx)) * m_conv
        my = abs(float(reaction.my)) * m_conv
        return LoadEffects(Pu=vertical * f_conv, Mu=max(my, mx), Mu2=my, Mu3=mx, Vu=horizontal * f_conv)
    vertical = float(reaction.fy)
    horizontal = abs(float(reaction.fx))
    mz = abs(float(reaction.mz)) * m_conv
    return LoadEffects(Pu=vertical * f_conv, Mu=mz, Mu2=mz, Vu=horizontal * f_conv)


def _design_footings(
    model: StructuralModel,
    analysis_result: AnalysisResult,
    service_results: Sequence[AnalysisResult],
    allowable_bearing_pressure: float,
    footing_cover: float,
    units: Any,
    code: Any,
) -> Dict[str, Any]:
    """
    An isolated spread footing under each supported column: base area for the allowable soil pressure under the
    service-level reactions (``service_results``, one per service combination), strength for the factored reactions
    of ``analysis_result`` (ACI 318-25 R13.2.6.1). The footing takes the concrete and bars of the column it carries.
    Inputs in model units; results keyed 'F<node>'.
    """
    from aci318.foundations.isolated import size_isolated_footing
    from struct_core import classify_frame_members

    is_metric = bool(getattr(units, "is_metric", False))
    is_3d = any(getattr(n, "z", 0.0) != 0.0 for n in model.nodes) or any(s.uz for s in model.supports)
    f_conv = conversion_factor(units, _KIP_IN, "force")
    m_conv = conversion_factor(units, _KIP_IN, "moment")
    q_allow = allowable_bearing_pressure * conversion_factor(units, "kip, ft", "pressure")
    cover_in = footing_cover * conversion_factor(units, _KIP_IN, "length")
    # Dimension grid: 0.1 m sides and 0.05 m thicknesses in metric models, 1 ft and 2 in otherwise
    grid = (dict(length_step=0.1 / 0.3048, min_length=1.2 / 0.3048, thickness_step=0.05 / 0.0254,
                 min_thickness=0.35 / 0.0254) if is_metric else {})
    materials = designed_section_materials(model, units)
    roles = classify_frame_members(model)

    footings: Dict[str, Any] = {}
    for support in model.supports:
        node_id = support.node_id
        factored_rxns = _support_reactions(analysis_result, node_id)
        column = (
            next((e for e in model.elements if e.type == "beam" and roles.get(e.id) == "column" and node_id in (e.start_node, e.end_node)), None)
            or next((e for e in model.elements if e.type == "beam" and node_id in (e.start_node, e.end_node)), None)
        )
        if not factored_rxns or column is None:
            continue
        factored_loads = [
            ld for ld in (_footing_load(r, is_3d, f_conv, m_conv) for r in factored_rxns)
            if not (abs(ld.Pu) <= 1e-9 and ld.Mu <= 1e-9 and ld.Vu <= 1e-9)
        ]
        if not factored_loads:
            continue
        service = [
            _footing_load(r, is_3d, f_conv, m_conv)
            for res in service_results
            for r in _support_reactions(res, node_id)
        ]
        if not service:
            raise ValueError(f"No service-level reaction at support node {node_id!r} for its footing")
        section = model.get_section(column.section_id)
        b, h, dia, circular = _section_dimensions(section, units=units)
        mats = materials[section.id]
        ftg = size_isolated_footing(
            service, q_allow, dia if circular else b, dia if circular else h, mats.concrete, mats.steel, code,
            cover=cover_in, member_id=f"F{node_id}", **grid,
        )
        results = [ftg.design(ld, service_loads=service) for ld in factored_loads]
        result = max(
            results,
            key=lambda r: (
                r.status == "Failed",
                max(
                    r.flexure_x.demand_capacity_ratio,
                    r.flexure_y.demand_capacity_ratio,
                    r.one_way_shear.demand_capacity_ratio,
                    r.punching_shear.demand_capacity_ratio,
                    r.max_bearing_pressure / r.allowable_bearing_capacity if r.allowable_bearing_capacity > 0 else 0.0,
                ),
            ),
        )
        footings[f"F{node_id}"] = result
    return footings


@dataclass
class _SectionMaterials:
    """Design materials of one reinforced-concrete section, in kip and inches."""

    concrete: Concrete
    steel: Steel   # longitudinal bars
    fyt: float     # yield strength of the transverse reinforcement (ksi)
    cover: float   # clear cover to the transverse reinforcement (in)


_KIP_IN = PRESETS["kip, in, s, °F"]


def _section_materials(model: StructuralModel, section: Any, units: Any) -> _SectionMaterials:
    """
    The concrete, bar steels and cover a section names, converted from the model units to kip and inches.

    A section designed as reinforced concrete must name a ``ConcreteMaterial`` (f'c, E, density), longitudinal and
    transverse ``RebarMaterial`` s (fy, Es) and its clear ``cover``; a missing one raises ``ValueError`` naming the
    section. Nothing is assumed: the tool that builds the model applies (and reports) any default.
    """
    problems: List[str] = []
    concrete_mat = model.get_material(section.material_id)
    if getattr(concrete_mat, "type", None) != "concrete":
        found = "is missing" if concrete_mat is None else f"is a '{concrete_mat.type}' material"
        problems.append(f"its material '{section.material_id}' {found}, not concrete (f'c)")
    bars = {}
    for field_name, role in (("rebar_material_id", "longitudinal"), ("transverse_rebar_material_id", "transverse")):
        material_id = getattr(section, field_name, None)
        bar = model.get_material(material_id)
        if getattr(bar, "type", None) != "rebar":
            problems.append(f"no {role} rebar material ({field_name}" + (f" '{material_id}')" if material_id else ")"))
        bars[role] = bar
    if getattr(section, "cover", None) is None:
        problems.append("no clear cover (cover)")
    if problems:
        raise ValueError(f"Section '{section.id}' cannot be designed as reinforced concrete: " + "; ".join(problems))

    to_ksi = conversion_factor(units, _KIP_IN, "stress")
    unit_weight = concrete_mat.unit_weight
    if unit_weight is None:  # weight density from the mass density, as the self-weight load does
        unit_weight = concrete_mat.rho * units.consistent_mass_factor * units.gravity_acceleration
    density_pcf = unit_weight * conversion_factor(units, "lbf, ft", "weight_density")
    if density_pcf <= 0.0:
        raise ValueError(f"Section '{section.id}': concrete '{concrete_mat.id}' has no density (unit_weight or rho)")
    # lambda from the equilibrium density (ACI 318-25 Table 19.2.4.1(a)): 1.0 above 135 pcf
    concrete = Concrete(fc=concrete_mat.fc * to_ksi, density=density_pcf,
                        concrete_type="normalweight" if density_pcf > 135.0 else "lightweight")
    concrete.Ec = concrete_mat.E * to_ksi  # the modulus the analysis used
    longitudinal, transverse = bars["longitudinal"], bars["transverse"]
    return _SectionMaterials(
        concrete=concrete,
        steel=Steel(fy=longitudinal.fy * to_ksi, Es=longitudinal.E * to_ksi),
        fyt=transverse.fy * to_ksi,
        cover=section.cover * conversion_factor(units, _KIP_IN, "length"),
    )


def designed_section_materials(
    model: StructuralModel, units: Any, element_ids: Optional[Iterable[Any]] = None
) -> Dict[Any, _SectionMaterials]:
    """``_section_materials`` of the sections of every frame element (or of ``element_ids``), by section ID; one
    ``ValueError`` lists every section that lacks a design input."""
    wanted = None if element_ids is None else set(element_ids)
    found: Dict[Any, _SectionMaterials] = {}
    problems: List[str] = []
    for element in model.elements:
        if element.type not in ("beam", "truss") or (wanted is not None and element.id not in wanted):
            continue
        section = model.get_section(element.section_id)
        if section is None:
            problems.append(f"Element '{element.id}' references missing section '{element.section_id}'")
            continue
        if section.id in found:
            continue
        try:
            found[section.id] = _section_materials(model, section, units)
        except ValueError as exc:
            if str(exc) not in problems:
                problems.append(str(exc))
    if problems:
        raise ValueError("\n".join(problems))
    return found


def _section_dimensions(sec_schema: Any, units: Optional[Any] = None) -> Tuple[float, float, float, bool]:
    """Return (b, h, diameter, is_circular) in inches for a struct_core section schema."""
    if sec_schema is None:
        raise ValueError("Section schema is required to determine dimensions.")
    if units is None:
        raise ValueError("Units are required to determine section dimensions.")

    len_scale = conversion_factor(units, PRESETS["kip, in, s, °F"], "length")

    if hasattr(sec_schema, "b") and hasattr(sec_schema, "h"):
        return float(sec_schema.b) * len_scale, float(sec_schema.h) * len_scale, 0.0, False
    if hasattr(sec_schema, "d"):
        return 0.0, 0.0, float(sec_schema.d) * len_scale, True

    raise ValueError(f"Unsupported section schema for ACI 318 design: {type(sec_schema).__name__}")
