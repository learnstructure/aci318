import math
from typing import List, Optional, Tuple, Union
from aci318.loads.load_effects import LoadEffects
from aci318.results.interaction import InteractionResult, PMInteractionResult
from aci318.sections.circle import CircularSection
from aci318.strength.axial_strength import AxialStrength
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class InteractionStrength(StrengthChecker):
    """
    P-M Interaction Diagram Generator and Strength Checker (ACI 318-19 §22.2, §22.4 & §10.5).
    
    Supports:
    - Uniaxial P-M interaction (Pu - Mu)
    - Biaxial P-M-M interaction (Pu - Mu2 - Mu3) via Bresler Reciprocal Load Method
      and Bresler / PCA Load Contour Method per ACI 318-19 Section 10.5.
    """

    def generate_pm_diagram(
        self,
        section: Optional[object] = None,
        num_points: int = 50,
    ) -> PMInteractionResult:
        """
        Generate P-M interaction diagram points for a section.
        
        Args:
            section: Target cross-section. If None, uses self.section.
            num_points: Number of points along the curve.
            
        Returns:
            PMInteractionResult containing nominal points and design (phi) points.
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

        points: List[Tuple[float, float]] = []  # (Mn, Pn)
        phi_points: List[Tuple[float, float]] = []  # (phi*Mn, phi*Pn)

        # Pure compression point
        axial_checker = AxialStrength(sec, self.code)
        axial_res = axial_checker.check(LoadEffects(Pu=0.0))
        po_nominal = axial_res.pn_nominal
        pn_max = axial_res.pn_max
        phi_pn_max = axial_res.phi_pn_max

        points.append((0.0, pn_max))
        phi_points.append((0.0, phi_pn_max))

        # Range of c values from h down to 0.05*h
        c_values = [h * 2.0] + [h * (1.0 - i / (num_points - 1)) for i in range(num_points)]

        for c in c_values:
            if c <= 0.001:
                continue

            a = min(beta_1 * c, h)
            cc = 0.85 * fc * a * b
            y_cc = h - a / 2.0

            pn = cc
            mn = cc * (y_cc - y_center)

            strain_t = 0.0
            d_max = 0.0

            for layer in sec.layers:
                eps_i = epsilon_cu * (c - layer.depth) / c
                fs_i = max(min(layer.steel.Es * eps_i, layer.steel.fy), -layer.steel.fy)

                if layer.depth > d_max:
                    d_max = layer.depth
                    strain_t = -eps_i  # tension positive

                force_i = layer.area * fs_i
                pn += force_i
                mn += force_i * (h - layer.depth - y_center)

            if pn > pn_max:
                continue

            phi = self.code.get_phi_flexure(max(strain_t, 0.0))
            phi_pn = phi * pn
            phi_mn = phi * abs(mn)

            if pn >= -po_nominal and abs(mn) >= 0.0:
                points.append((abs(mn), pn))
                phi_points.append((phi_mn, phi_pn))

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

        for i in range(len(phi_points) - 1):
            m1, p1 = phi_points[i]
            m2, p2 = phi_points[i + 1]

            if (p1 >= pu >= p2) or (p2 >= pu >= p1):
                if abs(p2 - p1) > 1e-4:
                    frac = (pu - p1) / (p2 - p1)
                    return max(0.0, m1 + frac * (m2 - m1))
                else:
                    return max(m1, m2)
        return max(m for m, _ in phi_points) if phi_points else 0.0

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

    def check(self, loads: LoadEffects) -> InteractionResult:
        """
        Check factored load demand (Pu, Mu, Mu2, Mu3) against column capacity.
        Automatically evaluates biaxial interaction when minor-axis moment Mu3 is present.
        """
        validate_load_effects(loads)

        pu = loads.Pu
        mux = abs(loads.Mu2 if loads.Mu2 != 0.0 else loads.Mu)
        muy = abs(loads.Mu3)

        # 1. Generate strong-axis PM diagram
        pm_res_x = self.generate_pm_diagram(num_points=35)
        if not pm_res_x.phi_points:
            return InteractionResult(
                axial_ratio=0.0,
                flexure_ratio=0.0,
                demand_capacity_ratio=0.0,
                status="Failed",
                messages=["Could not generate P-M interaction diagram."],
            )

        phi_pn_max = max(p for _, p in pm_res_x.phi_points)
        cap_mux = self._interpolate_capacity_mu(pm_res_x.phi_points, pu)

        # 2. Case A: Pure Uniaxial Bending (Muy is zero or negligible)
        if muy <= 1e-4:
            dcr = mux / cap_mux if cap_mux > 0.0 else (1.5 if mux > 0 else 0.0)
            status = "Passed"
            messages = []
            if dcr > 1.0:
                status = "Failed"
                messages.append(f"P-M Interaction demand/capacity ratio {dcr:.2f} exceeds 1.0.")
            elif dcr > 0.9:
                status = "Warning"
                messages.append(f"P-M Interaction demand/capacity ratio {dcr:.2f} is near capacity.")

            return InteractionResult(
                axial_ratio=pu / max(phi_pn_max, 1.0),
                flexure_ratio=mux / max(cap_mux, 1.0),
                demand_capacity_ratio=dcr,
                status=status,
                messages=messages,
                phi_mn_x=cap_mux,
                method_used="Uniaxial P-M Interaction (ACI 318-19 §22.4)",
            )

        # 3. Case B: Biaxial Bending (both Mux and Muy present)
        # Circular columns: resultant moment vector
        if isinstance(self.section, CircularSection):
            mu_res = math.hypot(mux, muy)
            dcr = mu_res / cap_mux if cap_mux > 0.0 else (1.5 if mu_res > 0 else 0.0)
            status = "Passed"
            messages = []
            if dcr > 1.0:
                status = "Failed"
                messages.append(f"Biaxial P-M interaction ratio {dcr:.2f} exceeds 1.0.")
            elif dcr > 0.9:
                status = "Warning"
                messages.append(f"Biaxial P-M interaction ratio {dcr:.2f} is near capacity.")

            return InteractionResult(
                axial_ratio=pu / max(phi_pn_max, 1.0),
                flexure_ratio=mu_res / max(cap_mux, 1.0),
                demand_capacity_ratio=dcr,
                status=status,
                messages=messages,
                phi_mn_x=cap_mux,
                phi_mn_y=cap_mux,
                biaxial_ratio=dcr,
                method_used="Circular Resultant Moment Interaction (ACI 318-19)",
            )

        # Rectangular columns: evaluate weak-axis capacity
        sec_y = getattr(self.section, "get_weak_axis_section", lambda: self.section)()
        pm_res_y = self.generate_pm_diagram(section=sec_y, num_points=35)
        cap_muy = self._interpolate_capacity_mu(pm_res_y.phi_points, pu)

        # Ratio components
        rx = mux / max(cap_mux, 1e-4) if cap_mux > 0.0 else (1.5 if mux > 0 else 0.0)
        ry = muy / max(cap_muy, 1e-4) if cap_muy > 0.0 else (1.5 if muy > 0 else 0.0)

        # Method 1: Bresler Load Contour Interaction (PCA / Parme Method)
        # Exponent alpha: typically 1.15 to 1.5 based on Pu / (phi*P0)
        ag = self.section.gross_area
        fc = self.section.concrete.fc
        ast = sum(lyr.area for lyr in self.section.layers) if self.section.layers else 0.0
        fy = self.section.layers[0].steel.fy if self.section.layers else 60.0
        phi_p0 = 0.65 * (0.85 * fc * (ag - ast) + fy * ast)
        beta_0 = pu / max(phi_p0, 1.0)
        alpha = 1.0 + min(0.5, max(0.15, beta_0))

        dcr_contour = (rx ** alpha + ry ** alpha) ** (1.0 / alpha)

        # Method 2: Bresler Reciprocal Load Method (ACI 318-19 Section 10.5.2)
        # 1/phi*Pn = 1/phi*Pnx + 1/phi*Pny - 1/phi*P0  (applicable when Pu >= 0.10 * phi * fc * Ag)
        min_pu_bresler = 0.10 * 0.65 * fc * ag
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

        governing_dcr = dcr_contour
        method_desc = f"Bresler Load Contour Method (alpha={alpha:.2f}, ACI 318-19 §10.5)"
        if dcr_bresler is not None and dcr_bresler > dcr_contour:
            governing_dcr = dcr_bresler
            method_desc = "Bresler Reciprocal Load Method (ACI 318-19 §10.5.2)"

        status = "Passed"
        messages = []
        if governing_dcr > 1.0:
            status = "Failed"
            messages.append(f"Biaxial P-M-M interaction ratio {governing_dcr:.2f} exceeds 1.0.")
        elif governing_dcr > 0.9:
            status = "Warning"
            messages.append(f"Biaxial P-M-M interaction ratio {governing_dcr:.2f} is near capacity.")

        return InteractionResult(
            axial_ratio=pu / max(phi_pn_max, 1.0),
            flexure_ratio=max(rx, ry),
            demand_capacity_ratio=round(governing_dcr, 3),
            status=status,
            messages=messages,
            phi_mn_x=round(cap_mux, 2),
            phi_mn_y=round(cap_muy, 2),
            biaxial_ratio=round(governing_dcr, 3),
            method_used=method_desc,
        )
