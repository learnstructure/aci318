import math
from typing import Dict, List, Optional, Sequence, Tuple, Union
from aci318.loads.load_effects import LoadEffects
from aci318.results.interaction import InteractionResult, PMInteractionResult
from aci318.sections.circle import CircularSection
from aci318.strength.axial_strength import AxialStrength
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class InteractionStrength(StrengthChecker):
    """
    P-M Interaction Diagram Generator and Strength Checker (ACI 318 §22.2, §22.4, §21.2.2 & §10.5).

    Supports:
    - Uniaxial P-M interaction (Pu - Mu)
    - Biaxial P-M-M interaction (Pu - Mu2 - Mu3) via Bresler Reciprocal Load Method
      and Bresler / PCA Load Contour Method.
    - Checking many concurrent load sets against one pair of diagrams (``check_load_sets``).

    Strength reduction factors come from ``code.get_phi_axial_flexure``, which applies the
    ACI 318-25 §21.2.2.3 limit between 0.10 f'c Ag and Pn,bal.
    """

    def __init__(self, section, code, spiral: bool = False) -> None:
        super().__init__(section, code)
        self.spiral = spiral
        self._diagrams: Dict[int, PMInteractionResult] = {}

    def _diagram(self, section) -> PMInteractionResult:
        """P-M diagram of ``section``, generated once per checker."""
        key = id(section)
        if key not in self._diagrams:
            self._diagrams[key] = self.generate_pm_diagram(section=section, num_points=35)
        return self._diagrams[key]

    def generate_pm_diagram(
        self,
        section: Optional[object] = None,
        num_points: int = 50,
    ) -> PMInteractionResult:
        """
        Generate P-M interaction diagram points for a section by strain compatibility (§22.2).

        Compression bars inside the equivalent stress block displace concrete (fs - 0.85 f'c).
        Points above Pn,max (Table 22.4.2.1) are cut off at Pn,max.

        Args:
            section: Target cross-section. If None, uses self.section.
            num_points: Number of neutral-axis depths sampled between h and 0.

        Returns:
            PMInteractionResult containing nominal points and design (phi) points, ordered from
            pure compression to pure tension (kip-in, kip; compression positive).
        """
        sec = section or self.section
        b = getattr(sec, "b_w", getattr(sec, "b", 12.0))
        h = sec.h
        fc = sec.concrete.fc
        beta_1 = self.code.get_beta_1(fc)
        epsilon_cu = getattr(sec.concrete, "max_strain", 0.003)
        y_center = h / 2.0

        if not sec.layers:
            return PMInteractionResult(points=[], phi_points=[], status="Failed", messages=["No rebar layers."])

        fy = sec.layers[0].steel.fy
        d_t = max(layer.depth for layer in sec.layers)

        def section_forces(c: float) -> Tuple[float, float, float]:
            """Nominal (Pn, Mn about the centroid, net tensile strain) for neutral-axis depth c."""
            a = min(beta_1 * c, h)
            cc = 0.85 * fc * a * b
            pn = cc
            mn = cc * (y_center - a / 2.0)
            for layer in sec.layers:
                eps_i = epsilon_cu * (c - layer.depth) / c
                fs_i = max(min(layer.steel.Es * eps_i, layer.steel.fy), -layer.steel.fy)
                if fs_i > 0.0 and layer.depth < a:
                    fs_i -= 0.85 * fc  # bar displaces concrete already counted in the stress block
                force_i = layer.area * fs_i
                pn += force_i
                mn += force_i * (y_center - layer.depth)
            strain_t = epsilon_cu * (d_t - c) / c
            return pn, abs(mn), strain_t

        axial_res = AxialStrength(sec, self.code, spiral=self.spiral).check(LoadEffects(Pu=0.0))
        pn_max = axial_res.pn_max
        pn_low = 0.10 * fc * sec.gross_area
        c_bal = epsilon_cu * d_t / (epsilon_cu + self.code.get_epsilon_ty(fy))
        pn_bal = section_forces(c_bal)[0]

        points: List[Tuple[float, float]] = [(0.0, pn_max)]  # (Mn, Pn)
        phi_cc = self.code.get_phi_axial(compression=True, spiral=self.spiral)
        phi_points: List[Tuple[float, float]] = [(0.0, phi_cc * pn_max)]

        c_values = [h * 2.0] + [h * (1.0 - i / (num_points - 1)) for i in range(num_points)]
        for c in c_values:
            if c <= 0.001:
                continue
            pn, mn, strain_t = section_forces(c)
            phi = self.code.get_phi_axial_flexure(
                max(strain_t, 0.0), pn, pn_low, pn_bal, spiral=self.spiral, fy=fy
            )
            pn_capped = min(pn, pn_max)
            points.append((mn, pn_capped))
            phi_points.append((phi * mn, phi * pn_capped))

        # Pure tension point (Pn = -Ast * fy, phi = 0.90)
        p_nt = sum(lyr.area * lyr.steel.fy for lyr in sec.layers)
        points.append((0.0, -p_nt))
        phi_points.append((0.0, -0.90 * p_nt))

        return PMInteractionResult(
            points=points,
            phi_points=phi_points,
            status="Passed",
            messages=[],
        )

    @staticmethod
    def _interpolate_capacity_mu(phi_points: List[Tuple[float, float]], pu: float) -> float:
        """Find design moment capacity phi*Mn for a given axial load Pu."""
        if not phi_points:
            return 0.0

        p_vals = [p for _, p in phi_points]
        p_max = max(p_vals)
        p_min = min(p_vals)
        if pu > p_max or pu < p_min:
            return 0.0

        best = 0.0
        for i in range(len(phi_points) - 1):
            m1, p1 = phi_points[i]
            m2, p2 = phi_points[i + 1]

            if (p1 >= pu >= p2) or (p2 >= pu >= p1):
                if abs(p2 - p1) > 1e-4:
                    frac = (pu - p1) / (p2 - p1)
                    best = max(best, m1 + frac * (m2 - m1))
                else:
                    best = max(best, m1, m2)
        return best

    @staticmethod
    def _interpolate_capacity_pu_for_eccentricity(
        phi_points: List[Tuple[float, float]],
        eccentricity: float,
    ) -> float:
        """
        Find design axial capacity phi*Pn along a radial line corresponding to eccentricity e = M / P.
        Intersects ray M = e * P with the interaction envelope (phi*Mn, phi*Pn).
        """
        if not phi_points or eccentricity <= 0.0:
            return phi_points[0][1] if phi_points else 0.0

        for i in range(len(phi_points) - 1):
            m1, p1 = phi_points[i]
            m2, p2 = phi_points[i + 1]
            if p1 <= 0.0 and p2 <= 0.0:
                continue

            e1 = m1 / max(p1, 1e-4)
            e2 = m2 / max(p2, 1e-4)

            if (e1 <= eccentricity <= e2) or (e2 <= eccentricity <= e1):
                # Linear interpolation between segment endpoints
                if abs(e2 - e1) > 1e-4:
                    frac = (eccentricity - e1) / (e2 - e1)
                    p_cap = p1 + frac * (p2 - p1)
                    return max(0.0, p_cap)
                return max(p1, p2)

        return phi_points[0][1] if phi_points else 0.0

    def check_load_sets(self, load_sets: Sequence[LoadEffects]) -> InteractionResult:
        """
        Check concurrent load sets (e.g. every combination and station) and return the governing result.

        Each set carries the axial force and the moments acting together at one section, so axial
        tension is never paired with a compression capacity. Diagrams are generated once.
        """
        if not load_sets:
            raise ValueError("check_load_sets requires at least one load set.")
        results = [self.check(loads) for loads in load_sets]
        return max(results, key=lambda r: r.demand_capacity_ratio)

    def check(self, loads: LoadEffects) -> InteractionResult:
        """
        Check factored load demand (Pu, Mu, Mu2, Mu3) against column capacity.
        Automatically evaluates biaxial interaction when minor-axis moment Mu3 is present.
        """
        validate_load_effects(loads)

        pu = loads.Pu
        mux = abs(loads.Mu2 if loads.Mu2 != 0.0 else loads.Mu)
        muy = abs(loads.Mu3)

        # 1. Strong-axis PM diagram
        pm_res_x = self._diagram(self.section)
        if not pm_res_x.phi_points:
            return InteractionResult(
                axial_ratio=0.0,
                flexure_ratio=0.0,
                demand_capacity_ratio=0.0,
                status="Failed",
                messages=["Could not generate P-M interaction diagram."],
            )

        phi_pn_max = max(p for _, p in pm_res_x.phi_points)
        phi_pn_min = min(p for _, p in pm_res_x.phi_points)

        # Axial demand-capacity ratio
        if pu >= 0.0:
            axial_ratio = pu / max(phi_pn_max, 1e-4)
        else:
            axial_ratio = abs(pu) / max(abs(phi_pn_min), 1e-4)

        messages = []
        if pu > phi_pn_max:
            return InteractionResult(
                axial_ratio=axial_ratio,
                flexure_ratio=0.0,
                demand_capacity_ratio=max(axial_ratio, 1.5),
                status="Failed",
                messages=[f"Factored axial compression Pu={pu:.1f} kip exceeds maximum design axial capacity phi*Pn,max={phi_pn_max:.1f} kip."],
                phi_mn_x=0.0,
                method_used="Axial Capacity Check (ACI 318 §22.4.2.1)",
            )
        elif pu < phi_pn_min:
            return InteractionResult(
                axial_ratio=axial_ratio,
                flexure_ratio=0.0,
                demand_capacity_ratio=max(axial_ratio, 1.5),
                status="Failed",
                messages=[f"Factored axial tension Pu={pu:.1f} kip exceeds design tension capacity phi*Pnt={abs(phi_pn_min):.1f} kip."],
                phi_mn_x=0.0,
                method_used="Axial Tension Check (ACI 318 §22.4.3)",
            )

        cap_mux = self._interpolate_capacity_mu(pm_res_x.phi_points, pu)

        # 2. Case A: Pure Uniaxial Bending (Muy is zero or negligible)
        if muy <= 1e-4:
            flexure_ratio = (mux / cap_mux) if cap_mux > 0.0 else (0.0 if mux == 0.0 else 999.0)
            dcr = max(axial_ratio, flexure_ratio)
            status = "Passed"
            if dcr > 1.0:
                status = "Failed"
                messages.append(f"P-M Interaction demand/capacity ratio {dcr:.2f} exceeds 1.0.")
            elif dcr > 0.9:
                status = "Warning"
                messages.append(f"P-M Interaction demand/capacity ratio {dcr:.2f} is near capacity.")

            return InteractionResult(
                axial_ratio=axial_ratio,
                flexure_ratio=flexure_ratio,
                demand_capacity_ratio=dcr,
                status=status,
                messages=messages,
                phi_mn_x=cap_mux,
                method_used="Uniaxial P-M Interaction (ACI 318 §22.4)",
            )

        # 3. Case B: Biaxial Bending (both Mux and Muy present)
        # Circular columns: resultant moment vector
        if isinstance(self.section, CircularSection):
            mu_res = math.hypot(mux, muy)
            flexure_ratio = (mu_res / cap_mux) if cap_mux > 0.0 else (0.0 if mu_res == 0.0 else 999.0)
            dcr = max(axial_ratio, flexure_ratio)
            status = "Passed"
            if dcr > 1.0:
                status = "Failed"
                messages.append(f"Biaxial P-M interaction ratio {dcr:.2f} exceeds 1.0.")
            elif dcr > 0.9:
                status = "Warning"
                messages.append(f"Biaxial P-M interaction ratio {dcr:.2f} is near capacity.")

            return InteractionResult(
                axial_ratio=axial_ratio,
                flexure_ratio=flexure_ratio,
                demand_capacity_ratio=dcr,
                status=status,
                messages=messages,
                phi_mn_x=cap_mux,
                phi_mn_y=cap_mux,
                biaxial_ratio=dcr,
                method_used="Circular Resultant Moment Interaction (ACI 318)",
            )

        # Rectangular columns: evaluate weak-axis capacity
        if not hasattr(self, "_weak_section"):
            self._weak_section = getattr(self.section, "get_weak_axis_section", lambda: self.section)()
        pm_res_y = self._diagram(self._weak_section)
        cap_muy = self._interpolate_capacity_mu(pm_res_y.phi_points, pu)

        # Ratio components
        rx = mux / max(cap_mux, 1e-4) if cap_mux > 0.0 else (1.5 if mux > 0 else 0.0)
        ry = muy / max(cap_muy, 1e-4) if cap_muy > 0.0 else (1.5 if muy > 0 else 0.0)

        # Method 1: Bresler Load Contour Interaction (PCA / Parme Method)
        ag = self.section.gross_area
        fc = self.section.concrete.fc
        ast = sum(lyr.area for lyr in self.section.layers) if self.section.layers else 0.0
        fy = self.section.layers[0].steel.fy if self.section.layers else 60.0
        phi_cc = self.code.get_phi_axial(compression=True, spiral=self.spiral)
        phi_p0 = phi_cc * (0.85 * fc * (ag - ast) + fy * ast)
        beta_0 = pu / max(phi_p0, 1.0)
        alpha = 1.0 + min(0.5, max(0.15, beta_0))

        dcr_contour = (rx ** alpha + ry ** alpha) ** (1.0 / alpha)

        # Method 2: Bresler Reciprocal Load Method (valid for Pn >= 0.10 f'c Ag)
        min_pu_bresler = 0.10 * phi_cc * fc * ag
        dcr_bresler = None
        if pu >= min_pu_bresler:
            ex = muy / max(pu, 1e-4)
            ey = mux / max(pu, 1e-4)
            phi_pnx = self._interpolate_capacity_pu_for_eccentricity(pm_res_x.phi_points, ey)
            phi_pny = self._interpolate_capacity_pu_for_eccentricity(pm_res_y.phi_points, ex)

            if phi_pnx > 0.0 and phi_pny > 0.0 and phi_p0 > 0.0:
                inv_pn = (1.0 / phi_pnx) + (1.0 / phi_pny) - (1.0 / phi_p0)
                if inv_pn > 0.0:
                    phi_pn_bresler = 1.0 / inv_pn
                    dcr_bresler = pu / phi_pn_bresler

        governing_dcr = max(axial_ratio, dcr_contour)
        method_desc = f"Bresler Load Contour Method (alpha={alpha:.2f})"
        if dcr_bresler is not None and dcr_bresler > dcr_contour:
            governing_dcr = max(axial_ratio, dcr_bresler)
            method_desc = "Bresler Reciprocal Load Method"

        status = "Passed"
        if governing_dcr > 1.0:
            status = "Failed"
            messages.append(f"Biaxial P-M-M interaction ratio {governing_dcr:.2f} exceeds 1.0.")
        elif governing_dcr > 0.9:
            status = "Warning"
            messages.append(f"Biaxial P-M-M interaction ratio {governing_dcr:.2f} is near capacity.")

        return InteractionResult(
            axial_ratio=axial_ratio,
            flexure_ratio=max(rx, ry),
            demand_capacity_ratio=round(governing_dcr, 3),
            status=status,
            messages=messages,
            phi_mn_x=round(cap_mux, 2),
            phi_mn_y=round(cap_muy, 2),
            biaxial_ratio=round(governing_dcr, 3),
            method_used=method_desc,
        )
