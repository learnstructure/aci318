"""
Frame-level ACI 318-25 provisions for cast-in-place moment frames:

- Chapter 15: beam-column joint shear (all frames; Vu from beam nominal strengths, 15.4.2.1(b)).
- Section 18.3: ordinary moment frames (joint shear with Mn, 18.3.4; short-column shear, 18.3.3).
- Section 18.4: intermediate moment frames (beam and column shear from nominal moment
  strengths, 18.4.2.3(a) and 18.4.3.1(a); hoop spacing; joints, 18.4.4).
- Sections 18.6-18.8: special moment frames (beam dimensions and reinforcement ratio, capacity-design
  shear from probable moments Mpr with Vc = 0 where applicable, strong-column/weak-beam,
  column dimensions, confinement Ash, column capacity shear, joint depth, and joint shear).

Inputs are inch-pound (kip, in, ksi). Beams carry the designed bar layout on both faces (the
member design covers moments of both signs with one layout), so Mn+ = Mn- and 18.6.3.2 / 18.4.2.2
are satisfied by construction. For rectangular columns whose orientation in the frame is not
known, the smaller dimension and the weaker-axis strength are used (conservative).

Where 18.4.2.3 and 18.4.3.1 allow the lesser of (a) capacity shear and (b) amplified-E analysis
shear, (a) is used, which is the larger demand. Column Pu ranges include all combinations, so the
lowest Mn (18.7.3.2) and the highest Mpr (18.7.6.1) are taken over a range that contains the
seismic combinations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from aci318.codes.base import DesignCode
from aci318.database.bars import BAR_DATABASE
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.column_reinforcement import (
    MAX_SUPPORTED_SPACING_HIGH_AXIAL,
    max_supported_bar_spacing,
    perimeter_bar_spacing,
)
from aci318.sections.rectangle import DEFAULT_COVER, RectangleSection
from aci318.strength.flexure_strength import FlexureStrength
from aci318.strength.interaction_strength import InteractionStrength

SYSTEMS = ("smf", "imf", "omf", "none")
PRACTICAL_MIN_SPACING = 3.0


@dataclass
class SeismicCheck:
    """One code check: demand / capacity with the governing clause."""

    clause: str
    description: str
    demand: float
    capacity: float
    member_id: Optional[str] = None
    messages: List[str] = field(default_factory=list)

    @property
    def dcr(self) -> float:
        if self.capacity <= 0.0:
            return math.inf if self.demand > 0.0 else 0.0
        return self.demand / self.capacity

    @property
    def passed(self) -> bool:
        return self.dcr <= 1.0


@dataclass
class FrameBeam:
    id: str
    b: float                 # web width (in)
    h: float                 # overall depth (in)
    d: float                 # effective depth (in)
    clear_span: float        # ln (in)
    n_bars: int              # bars per face
    bar_size: str
    concrete: Concrete
    wu: float                # factored gravity load along the span (kip/in)
    direction: str           # 'x' or 'y'
    fy: float = 60.0
    fyt: float = 60.0
    cover: float = DEFAULT_COVER  # clear cover to the stirrups (in)
    # Factored-analysis moment the beam applies to each end joint (kip-in), signed about the joint's
    # horizontal axis normal to the frame plane, per load combination: {joint id: {combination: M}}.
    # Used for Chapter 15 joint shear with continuous beams (15.4.2.1(a)).
    end_moments: Dict[str, Dict[str, float]] = field(default_factory=dict)


@dataclass
class FrameColumn:
    id: str
    section: RectangleSection          # with longitudinal layers (perimeter pattern)
    clear_height: float                # lu (in)
    pu_values: Sequence[float]         # factored axial forces, compression positive (kip)
    vu_analysis: float                 # largest factored shear from analysis (kip)
    bars_per_face: Tuple[int, int]     # (bars on each b-face, bars on each h-face)
    bar_size: str
    fyt: float = 60.0


@dataclass
class FrameJoint:
    id: str
    beams: Dict[str, List[str]]        # direction -> beam ids framing into the joint
    column_below: Optional[str]
    column_above: Optional[str]
    height_below: float = 0.0          # story height of the column below (in)
    height_above: float = 0.0          # story height of the column above (in)


# -----------------------------------------------------------------------------
# Strength helpers
# -----------------------------------------------------------------------------
def _db(size: str) -> float:
    return BAR_DATABASE[size]["diameter"]


def _ab(size: str) -> float:
    return BAR_DATABASE[size]["area"]


def beam_moment_strength(beam: FrameBeam, code: DesignCode, stress_factor: float = 1.0) -> float:
    """Nominal moment strength (kip-in) of the doubly reinforced beam with steel stress stress_factor * fy."""
    sec = RectangleSection(b=beam.b, h=beam.h, concrete=beam.concrete, cover=beam.cover)
    steel = Steel(fy=beam.fy * stress_factor)
    top = beam.cover + 0.375 + _db(beam.bar_size) / 2.0
    sec.add_rebar_layer(num_bars=beam.n_bars, bar_size=beam.bar_size, depth=top, steel=steel)
    sec.add_rebar_layer(num_bars=beam.n_bars, bar_size=beam.bar_size, depth=beam.d, steel=steel)
    return FlexureStrength(sec, code).check(LoadEffects(Mu=1.0)).nominal_moment


def _with_steel_factor(section: RectangleSection, factor: float) -> RectangleSection:
    sec = RectangleSection(b=section.b, h=section.h, concrete=section.concrete, cover=section.cover)
    n_b, n_h, size, cover, tie, steel = section.bar_pattern
    sec._place_perimeter_bars(n_b, n_h, size, cover, tie, Steel(fy=steel.fy * factor))
    return sec


def column_moment_strength(
    column: FrameColumn, code: DesignCode, pu: float, stress_factor: float = 1.0
) -> float:
    """Nominal moment strength (kip-in) at axial force pu, weaker of the two axes."""
    sec = _with_steel_factor(column.section, stress_factor)
    strengths = []
    for s in (sec, sec.get_weak_axis_section()):
        points = InteractionStrength(s, code).generate_pm_diagram(num_points=40).points
        strengths.append(InteractionStrength._interpolate_capacity_mu(points, pu))
    return min(strengths)


def _column_strength_range(column: FrameColumn, code: DesignCode, stress_factor: float, lowest: bool) -> float:
    values = [column_moment_strength(column, code, pu, stress_factor) for pu in _pu_samples(column)]
    return min(values) if lowest else max(values)


def _pu_samples(column: FrameColumn) -> List[float]:
    lo, hi = min(column.pu_values), max(column.pu_values)
    return [lo + (hi - lo) * i / 8.0 for i in range(9)] if hi > lo else [lo]


# -----------------------------------------------------------------------------
# Transverse reinforcement design
# -----------------------------------------------------------------------------
def _design_stirrups(
    v_required: float, vc: float, b: float, d: float, fc: float, fyt: float, s_max: float,
    options: Sequence[Tuple[str, int]], phi: float = 0.75,
) -> Tuple[str, int, float, float]:
    """
    Lightest stirrup/hoop arrangement resisting v_required with spacing <= s_max (>= 3 in).
    Returns (bar size, legs, spacing, phi*Vn). Vs is limited to 8 sqrt(f'c) b d (22.5.1.2).
    """
    vs_max = 8.0 * math.sqrt(fc * 1000.0) * b * d / 1000.0
    vs_req = max(v_required / phi - vc, 0.0)
    best = None
    for size, legs in options:
        av = legs * _ab(size)
        s_strength = av * fyt * d / vs_req if vs_req > 0.0 else math.inf
        s = math.floor(min(s_strength, s_max) * 2.0) / 2.0
        if s >= PRACTICAL_MIN_SPACING:
            vs = min(av * fyt * d / s, vs_max)
            return size, legs, s, phi * (vc + vs)
        vs = min(av * fyt * d / PRACTICAL_MIN_SPACING, vs_max)
        if best is None or vs > best[3]:
            best = (size, legs, PRACTICAL_MIN_SPACING, vs)
    size, legs, s, vs = best
    return size, legs, s, phi * (vc + vs)


def _beam_options(b: float) -> List[Tuple[str, int]]:
    options = [("#3", 2), ("#4", 2), ("#5", 2)]
    if b >= 12.0:
        options += [("#4", 4), ("#5", 4)]
    return options


# -----------------------------------------------------------------------------
# Beams
# -----------------------------------------------------------------------------
def check_beam(beam: FrameBeam, code: DesignCode, system: str, sds: float) -> List[SeismicCheck]:
    """Beam checks of 18.6 (SMF) or 18.4 (IMF). OMF beams (18.3.2) need two bars per face."""
    checks: List[SeismicCheck] = []
    fc = beam.concrete.fc
    lam = code.get_lambda_(beam.concrete)
    db = _db(beam.bar_size)
    if beam.n_bars < 2:
        checks.append(SeismicCheck("ACI 318-25 §18.3.2", "Beam: two continuous bars at top and bottom faces",
                                   2.0, float(beam.n_bars), beam.id))
    if system not in ("smf", "imf"):
        return checks

    if system == "smf":
        checks.append(SeismicCheck("ACI 318-25 §18.6.2.1(a)", "SMF beam: clear span ln >= 4d",
                                   4.0 * beam.d, beam.clear_span, beam.id))
        checks.append(SeismicCheck("ACI 318-25 §18.6.2.1(b)", "SMF beam: width bw >= max(0.3h, 10 in)",
                                   max(0.3 * beam.h, 10.0), beam.b, beam.id))
        rho = beam.n_bars * _ab(beam.bar_size) / (beam.b * beam.d)
        rho_max = 0.025 if beam.fy <= 60.0 else 0.02
        checks.append(SeismicCheck("ACI 318-25 §18.6.3.1", "SMF beam: reinforcement ratio rho <= 0.025 (Grade 60)",
                                   rho, rho_max, beam.id))
        stress_factor, s_max = 1.25, min(beam.d / 4.0, 6.0, (6.0 if beam.fy <= 60.0 else 5.0) * db)
        clause = "ACI 318-25 §18.6.5"
    else:
        stress_factor, s_max = 1.0, min(beam.d / 4.0, 8.0 * db, 24.0 * 0.375, 12.0)
        clause = "ACI 318-25 §18.4.2.3(a)"

    m_end = beam_moment_strength(beam, code, stress_factor)
    v_moment = 2.0 * m_end / beam.clear_span          # moments of opposite sign at both faces
    v_gravity = beam.wu * beam.clear_span / 2.0
    ve = v_moment + v_gravity
    vc_full = 2.0 * lam * math.sqrt(fc * 1000.0) * beam.b * beam.d / 1000.0
    # 18.6.5.2: Vc = 0 where the earthquake-induced shear is at least half of Ve (beam Pu < Ag f'c/20)
    vc = 0.0 if system == "smf" and v_moment >= 0.5 * ve else vc_full
    size, legs, s, phi_vn = _design_stirrups(ve, vc, beam.b, beam.d, fc, min(beam.fyt, 60.0), s_max, _beam_options(beam.b))
    # 21.2.4.1 (SMF): phi = 0.60 if Vn is less than the shear at nominal moment strength
    if system == "smf":
        vn = phi_vn / 0.75
        v_at_mn = 2.0 * beam_moment_strength(beam, code, 1.0) / beam.clear_span + v_gravity
        if vn < v_at_mn:
            phi_vn = 0.60 * vn
    checks.append(SeismicCheck(
        clause, f"{system.upper()} beam: capacity-design shear Ve at the hinge regions",
        ve, phi_vn, beam.id,
        [f"Ve = {ve:.1f} kip (moments {v_moment:.1f} + gravity {v_gravity:.1f}); "
         f"hoops {legs}-leg {size} @ {s:.1f} in within 2h of the joint faces; Vc = {vc:.1f} kip"],
    ))
    return checks


# -----------------------------------------------------------------------------
# Columns
# -----------------------------------------------------------------------------
def _hx(column: FrameColumn) -> float:
    """Largest center-to-center spacing of laterally supported longitudinal bars (all bars supported)."""
    return perimeter_bar_spacing(column.section.b, column.section.h, column.bars_per_face, column.bar_size,
                                 column.section.cover)


def check_column(
    column: FrameColumn, code: DesignCode, system: str, end_moment_limits: Sequence[Optional[float]] = (None, None)
) -> List[SeismicCheck]:
    """
    Column checks of 18.7 (SMF), 18.4.3 (IMF), or 18.3.3 (OMF).

    ``end_moment_limits`` are the moments the beams can deliver to the column at its two ends
    (from beam Mpr, 18.7.6.1.1), or None at an end without framing beams (e.g. a support).
    """
    if column.section.bar_pattern is None:
        raise ValueError(f"Column {column.id}: frame checks need a rectangular section with a perimeter bar pattern.")
    checks: List[SeismicCheck] = []
    sec = column.section
    fc = sec.concrete.fc
    ag = sec.gross_area
    c_min, c_max = min(sec.b, sec.h), max(sec.b, sec.h)
    db = _db(column.bar_size)
    lam = code.get_lambda_(sec.concrete)
    pu_min, pu_max = min(column.pu_values), max(column.pu_values)
    d = c_min - (sec.cover + 0.5 + db / 2.0)

    if system == "smf":
        checks.append(SeismicCheck("ACI 318-25 §18.7.2.1(a)", "SMF column: shortest dimension >= 12 in",
                                   12.0, c_min, column.id))
        checks.append(SeismicCheck("ACI 318-25 §18.7.2.1(b)", "SMF column: dimension ratio >= 0.4",
                                   0.4, c_min / c_max, column.id))
        ast = sum(lyr.area for lyr in sec.layers)
        checks.append(SeismicCheck("ACI 318-25 §18.7.4.1", "SMF column: Ast <= 0.06 Ag", ast, 0.06 * ag, column.id))
        hx = _hx(column)
        hx_limit = max_supported_bar_spacing("smf", pu_max, ag, fc)
        hx_clause = "(f)" if hx_limit == MAX_SUPPORTED_SPACING_HIGH_AXIAL else "(e)"
        checks.append(SeismicCheck(f"ACI 318-25 §18.7.5.2{hx_clause}",
                                   f"SMF column: spacing hx of supported bars <= {hx_limit:g} in",
                                   hx, hx_limit, column.id))
        # 18.7.5.3 spacing and Table 18.7.5.4 confinement
        so = min(max(4.0 + (14.0 - hx) / 3.0, 4.0), 6.0)
        s_conf = math.floor(min(c_min / 4.0, 6.0 * db, so) * 2.0) / 2.0
        b_core, h_core = sec.b - 2 * sec.cover, sec.h - 2 * sec.cover
        a_ch = b_core * h_core
        ratio = max(0.3 * (ag / a_ch - 1.0) * fc / column.fyt, 0.09 * fc / column.fyt)
        n_l = 2 * sum(column.bars_per_face) - 4
        if pu_max > 0.3 * ag * fc or fc > 10.0:
            kf = max(fc / 25.0 + 0.6, 1.0)
            kn = n_l / (n_l - 2)
            ratio = max(ratio, 0.2 * kf * kn * pu_max / (column.fyt * a_ch))
        # legs parallel to h cross bc = b_core and engage the bars of a b-face, and vice versa
        candidates = []
        for legs, bc in ((column.bars_per_face[0], b_core), (column.bars_per_face[1], h_core)):
            ash_req = ratio * s_conf * bc
            hoop = next((sz for sz in ("#3", "#4", "#5") if legs * _ab(sz) >= ash_req), "#5")
            candidates.append((ash_req, legs * _ab(hoop), f"{legs} legs of {hoop} @ {s_conf:.1f} in across bc = {bc:.1f} in"))
        demand, capacity, note = max(candidates, key=lambda c: c[0] / c[1])
        checks.append(SeismicCheck("ACI 318-25 §18.7.5.4", "SMF column: confinement Ash within lo",
                                   demand, capacity, column.id, [note]))
        stress_factor, clause = 1.25, "ACI 318-25 §18.7.6.1"
        s_max = s_conf
        m_col = _column_strength_range(column, code, stress_factor, lowest=False)
    elif system == "imf":
        stress_factor, clause = 1.0, "ACI 318-25 §18.4.3.1(a)"
        s_max = min(8.0 * db, 8.0, c_min / 2.0)
        m_col = _column_strength_range(column, code, 1.0, lowest=False)
    elif system == "omf":
        if column.clear_height > 5.0 * c_min:
            return checks
        stress_factor, clause = 1.0, "ACI 318-25 §18.3.3(a)"
        s_max = min(d / 2.0, 24.0)
        m_col = _column_strength_range(column, code, 1.0, lowest=False)
    else:
        return checks

    v_col = 2.0 * m_col / column.clear_height
    if system == "smf":
        end_moments = [m_col if lim is None else min(m_col, lim) for lim in end_moment_limits]
        v_capacity = sum(end_moments) / column.clear_height
    else:
        v_capacity = v_col
    ve = max(v_capacity, column.vu_analysis)
    beam_limited_shear = v_capacity if v_capacity < v_col else None
    vc_full = code.get_vc(fc, c_min, d, max(pu_min, 0.0), A_g=ag, A_v=1.0, A_v_min=0.0, lambda_val=lam)
    # 18.7.6.2.1: Vc = 0 where Pu < Ag f'c / 20 (the capacity shear is earthquake-induced)
    vc = 0.0 if system == "smf" and pu_min < ag * fc / 20.0 else vc_full
    legs = min(column.bars_per_face)
    options = [(sz, legs) for sz in ("#3", "#4", "#5")]
    size, n_legs, s, phi_vn = _design_stirrups(ve, vc, c_min, d, fc, min(column.fyt, 60.0), s_max, options)
    checks.append(SeismicCheck(
        clause, f"{system.upper()} column: capacity-design shear Ve",
        ve, phi_vn, column.id,
        [f"Ve = {ve:.1f} kip (column moments {v_col:.1f}"
         + (f", beam-limited {beam_limited_shear:.1f}" if beam_limited_shear is not None else "")
         + f", analysis {column.vu_analysis:.1f}); hoops {n_legs}-leg {size} @ {s:.1f} in; Vc = {vc:.1f} kip"],
    ))
    return checks


# -----------------------------------------------------------------------------
# Joints
# -----------------------------------------------------------------------------
_TABLE_15_5_2_1 = {(True, True, True): 24.0, (True, True, False): 20.0, (True, False, True): 20.0,
                   (True, False, False): 15.0, (False, True, True): 20.0, (False, True, False): 15.0,
                   (False, False, True): 15.0, (False, False, False): 12.0}
_TABLE_18_8_4_3 = {(True, True, True): 20.0, (True, True, False): 15.0, (True, False, True): 15.0,
                   (True, False, False): 12.0, (False, True, True): 15.0, (False, True, False): 12.0,
                   (False, False, True): 12.0, (False, False, False): 8.0}


def column_strength_for_strong_column(column: FrameColumn, code: DesignCode) -> float:
    """Column Mn for 18.7.3.2: the lowest over the factored axial forces, weaker axis (kip-in)."""
    return _column_strength_range(column, code, 1.0, lowest=True)


def strong_column_demand(
    joint: FrameJoint,
    direction: str,
    beams: Dict[str, FrameBeam],
    columns: Dict[str, FrameColumn],
    code: DesignCode,
) -> Optional[Tuple[float, float]]:
    """
    (1.2 sum(Mnb), sum(Mnc)) of the strong-column/weak-beam requirement (18.7.3.2) at ``joint`` for the
    beams framing in ``direction``, or None where it does not apply: no framing beams or columns, or
    the column ends at the joint and carries less than Ag f'c / 10 (18.7.3.1).
    """
    framing = [beams[b] for b in joint.beams.get(direction, []) if b in beams]
    present = [columns[c] for c in (joint.column_below, joint.column_above) if c in columns]
    if not framing or not present:
        return None
    col = present[0]
    continuous = joint.column_above is not None and joint.column_below is not None
    if not continuous and not (col.pu_values and max(col.pu_values) >= col.section.gross_area * col.section.concrete.fc / 10.0):
        return None
    m_nb = sum(beam_moment_strength(b, code, 1.0) for b in framing)
    return 1.2 * m_nb, sum(column_strength_for_strong_column(c, code) for c in present)


def check_joint(
    joint: FrameJoint,
    beams: Dict[str, FrameBeam],
    columns: Dict[str, FrameColumn],
    code: DesignCode,
    system: str,
) -> List[SeismicCheck]:
    """Joint shear (Chapter 15 / 18.3.4 / 18.4.4.7 / 18.8.4), joint depth (18.8.2.3, SMF),
    strong-column/weak-beam (18.7.3.2, SMF), and the strut-and-tie trigger (15.3.1)."""
    checks: List[SeismicCheck] = []
    col = columns.get(joint.column_below) or columns.get(joint.column_above)
    if col is None:
        return checks
    sec = col.section
    c_dim = min(sec.b, sec.h)
    fc = sec.concrete.fc
    lam = code.get_lambda_(sec.concrete)
    column_continuous = joint.column_above is not None and joint.column_below is not None
    stress_factor = 1.25 if system == "smf" else 1.0
    phi = 0.85 if system == "smf" else 0.75
    table, table_clause = (
        (_TABLE_18_8_4_3, "Table 18.8.4.3") if system in ("smf", "imf") else (_TABLE_15_5_2_1, "Table 15.5.2.1")
    )
    clause = {"smf": "ACI 318-25 §18.8.4", "imf": "ACI 318-25 §18.4.4.7",
              "omf": "ACI 318-25 §18.3.4"}.get(system, "ACI 318-25 §15.5")

    for direction, beam_ids in joint.beams.items():
        framing = [beams[b] for b in beam_ids if b in beams]
        if not framing:
            continue
        h_beam = max(b.h for b in framing)
        if h_beam > 2.0 * c_dim:
            checks.append(SeismicCheck("ACI 318-25 §15.3.1", f"Joint {joint.id} ({direction}): beam depth <= 2 x column depth (else strut-and-tie)",
                                       h_beam, 2.0 * c_dim, joint.id))
        if system == "smf":
            db_max = max(_db(b.bar_size) for b in framing)
            checks.append(SeismicCheck("ACI 318-25 §18.8.2.3", f"Joint {joint.id} ({direction}): joint depth >= max(20 db, h_beam/2)",
                                       max(20.0 / lam * db_max, 0.5 * h_beam), c_dim, joint.id))
            scwb = strong_column_demand(joint, direction, beams, columns, code)
            if scwb is not None:
                checks.append(SeismicCheck("ACI 318-25 §18.7.3.2", f"Joint {joint.id} ({direction}): strong column / weak beam sum(Mnc) >= 1.2 sum(Mnb)",
                                           *scwb, joint.id))

        beam_continuous = len(framing) >= 2
        heights = [h for h in (joint.height_below, joint.height_above) if h > 0.0]
        story_h = (sum(heights) / len(heights)) if column_continuous else max(heights)
        # Beam forces at the joint faces: Mn-based (15.4.2.1(b), 18.3.4, 18.4.4.7) or Mpr-based (18.8.2.1).
        # Frames outside Chapter 18 with continuous beams use the moments transferred in the factored-load
        # analysis (15.4.2.1(a)): per combination, each beam's signed joint moment M acts as a couple at the
        # lever arm jd = Mn / (As fy) of its reinforcement, so Vu = |sum M / jd| - |sum M| / story height.
        if system == "none" and beam_continuous and all(joint.id in b.end_moments for b in framing):
            arms = [beam_moment_strength(b, code, 1.0) / (b.fy * b.n_bars * _ab(b.bar_size)) for b in framing]
            combos = set.intersection(*(set(b.end_moments[joint.id]) for b in framing))
            tension, m_beams, vu = 0.0, 0.0, 0.0
            for combo in combos:
                moments = [b.end_moments[joint.id][combo] for b in framing]
                t_c = abs(sum(m / jd for m, jd in zip(moments, arms)))
                m_c = abs(sum(moments))
                if t_c - m_c / story_h >= vu:
                    tension, m_beams, vu = t_c, m_c, t_c - m_c / story_h
            basis = "factored-analysis moments (15.4.2.1(a))"
        else:
            m_beams = sum(beam_moment_strength(b, code, stress_factor) for b in framing)
            tension = sum(stress_factor * b.fy * b.n_bars * _ab(b.bar_size) for b in framing)
            vu = tension - m_beams / story_h
            basis = "probable moments Mpr (1.25 fy)" if system == "smf" else "nominal moments Mn"
        v_col = m_beams / story_h
        transverse = [beams[b] for d, ids in joint.beams.items() if d != direction for b in ids if b in beams]
        confined = len(transverse) >= 2 and all(
            t.b >= 0.75 * c_dim and t.b * t.h >= 0.75 * c_dim * h_beam for t in transverse
        )
        coef = table[(column_continuous, beam_continuous, confined)]
        bw = max(b.b for b in framing)
        a_j = c_dim * min(c_dim, bw + c_dim)
        vn = coef * lam * math.sqrt(fc * 1000.0) * a_j / 1000.0
        checks.append(SeismicCheck(
            clause, f"Joint {joint.id} ({direction}): joint shear", vu, phi * vn, joint.id,
            [f"Vu = {vu:.1f} kip (T = {tension:.1f}, Vcol = {v_col:.1f}; {basis}); Vn = {coef:g} lambda sqrt(f'c) Aj "
             f"({table_clause}; column {'continuous' if column_continuous else 'other'}, beam "
             f"{'continuous' if beam_continuous else 'other'}, {'confined' if confined else 'not confined'})"],
        ))
    return checks


def beam_end_moment_limits(
    column_id: str, joints: Sequence[FrameJoint], beams: Dict[str, FrameBeam], code: DesignCode
) -> List[Optional[float]]:
    """
    Moments the beams can deliver to each end of a column (18.7.6.1.1): the summed beam Mpr of
    the stronger framing direction at the end joint, shared equally between the columns meeting
    there. Ends without a joint or without framing beams give None.
    """
    limits: List[Optional[float]] = []
    for j in joints:
        if column_id not in (j.column_below, j.column_above):
            continue
        per_dir = [sum(beam_moment_strength(beams[b], code, 1.25) for b in ids if b in beams)
                   for ids in j.beams.values()]
        if not per_dir or max(per_dir) <= 0.0:
            limits.append(None)
            continue
        n_cols = sum(1 for c in (j.column_below, j.column_above) if c is not None)
        limits.append(max(per_dir) / n_cols)
    return (limits + [None, None])[:2]
