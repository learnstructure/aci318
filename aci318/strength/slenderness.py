"""
Slenderness (second-order) effects for columns per ACI 318-25 Section 6.6.4 (moment magnification).

The functions are unit-agnostic except :func:`minimum_eccentricity`, which follows the inch-pound
form of Eq. (6.6.4.5.4). Forces and lengths must be in one consistent unit system.
"""

from __future__ import annotations

import math

# §6.6.4.3(b): a story may be analyzed as nonsway if Q <= 0.05
NONSWAY_Q_LIMIT = 0.05
# §6.6.4.6.2: Eq. (a), delta_s = 1/(1 - Q), is permitted only while delta_s <= 1.5
SWAY_MAGNIFIER_EQ_A_LIMIT = 1.5
# §6.2.5.3: end moments including second-order effects shall not exceed 1.4 x first-order moments
SECOND_ORDER_MOMENT_RATIO_LIMIT = 1.4


def stability_index(sum_pu: float, delta_o: float, v_us: float, l_c: float) -> float:
    """
    Story stability index Q = sum(Pu) delta_o / (Vus lc), Eq. (6.6.4.4.1).

    Args:
        sum_pu: Total factored vertical load in the story.
        delta_o: First-order relative lateral deflection of the story under Vus.
        v_us: Factored horizontal story shear.
        l_c: Story height (center-to-center of joints).
    """
    if v_us <= 0.0 or l_c <= 0.0:
        raise ValueError("Story shear Vus and story height lc must be positive.")
    return max(sum_pu, 0.0) * abs(delta_o) / (v_us * l_c)


def sway_magnifier(q: float) -> float:
    """
    Sway moment magnifier delta_s = 1 / (1 - Q) >= 1, Eq. (6.6.4.6.2a).

    Returns ``inf`` when Q >= 1 (story unstable). Values above 1.5 are not permitted by
    §6.6.4.6.2 for Eq. (a); callers must report them.
    """
    if q >= 1.0:
        return math.inf
    return max(1.0 / (1.0 - q), 1.0)


def effective_stiffness(ec: float, ig: float, beta_dns: float) -> float:
    """(EI)eff = 0.4 Ec Ig / (1 + beta_dns), Eq. (6.6.4.4.4a)."""
    return 0.4 * ec * ig / (1.0 + max(beta_dns, 0.0))


def critical_buckling_load(ei_eff: float, k: float, l_u: float) -> float:
    """Pc = pi^2 (EI)eff / (k lu)^2, Eq. (6.6.4.4.2)."""
    if l_u <= 0.0 or k <= 0.0:
        raise ValueError("Unsupported length lu and effective length factor k must be positive.")
    return math.pi ** 2 * ei_eff / (k * l_u) ** 2


def equivalent_moment_factor(m_end_i: float, m_end_j: float) -> float:
    """
    Cm = 0.6 - 0.4 M1/M2, Eq. (6.6.4.5.3a), for a column without transverse loads between supports.

    ``m_end_i`` and ``m_end_j`` are the internal (beam-convention) moments at the two ends: equal
    signs mean single curvature (M1/M2 negative), opposite signs double curvature (M1/M2 positive).
    """
    m1, m2 = sorted((m_end_i, m_end_j), key=abs)
    if abs(m2) <= 0.0:
        return 1.0
    ratio = abs(m1) / abs(m2)
    single_curvature = m1 * m2 > 0.0
    return 0.6 + 0.4 * ratio if single_curvature else 0.6 - 0.4 * ratio


def member_magnifier(cm: float, pu: float, pc: float) -> float:
    """
    Member-curvature magnifier delta = Cm / (1 - Pu / (0.75 Pc)) >= 1.0, Eq. (6.6.4.5.2).

    Returns ``inf`` when Pu >= 0.75 Pc (member unstable). Tension (Pu <= 0) gives 1.0.
    """
    if pu <= 0.0:
        return 1.0
    if pc <= 0.0 or pu >= 0.75 * pc:
        return math.inf
    return max(cm / (1.0 - pu / (0.75 * pc)), 1.0)


def minimum_eccentricity(h_in: float) -> float:
    """Minimum eccentricity (0.6 + 0.03 h) in inches for M2,min = Pu (0.6 + 0.03 h), Eq. (6.6.4.5.4)."""
    return 0.6 + 0.03 * h_in
