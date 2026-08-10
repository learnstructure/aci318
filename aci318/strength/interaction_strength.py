import math
from typing import List, Tuple
from aci318.loads.load_effects import LoadEffects
from aci318.results.interaction import InteractionResult, PMInteractionResult
from aci318.strength.axial_strength import AxialStrength
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class InteractionStrength(StrengthChecker):
    """
    P-M Interaction Diagram Generator and Strength Checker (ACI 318-19 §22.2 & §22.4).
    
    Generates nominal (Pn, Mn) and design (phi*Pn, phi*Mn) strength curves for column cross-sections
    by stepping neutral axis depth c from pure compression down to pure tension.
    """

    def generate_pm_diagram(self, num_points: int = 50) -> PMInteractionResult:
        """
        Generate P-M interaction diagram points.
        
        Args:
            num_points: Number of points along the curve.
            
        Returns:
            PMInteractionResult containing nominal points and design (phi) points.
        """
        b = getattr(self.section, "b_w", getattr(self.section, "b", 12.0))
        h = self.section.h
        fc = self.section.concrete.fc
        beta_1 = self.code.get_beta_1(fc)
        epsilon_cu = getattr(self.section.concrete, "max_strain", 0.003)
        y_center = h / 2.0

        if not self.section.layers:
            return PMInteractionResult(points=[], phi_points=[], status="Failed", messages=["No rebar layers."])

        points: List[Tuple[float, float]] = []  # (Mn, Pn)
        phi_points: List[Tuple[float, float]] = []  # (phi*Mn, phi*Pn)

        # Pure compression point
        axial_checker = AxialStrength(self.section, self.code)
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

            for layer in self.section.layers:
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

    def check(self, loads: LoadEffects) -> InteractionResult:
        """
        Check factored load demand against column P-M capacity.
        
        Args:
            loads: LoadEffects object containing Pu (kip) and Mu (kip-in).
            
        Returns:
            InteractionResult dataclass.
        """
        validate_load_effects(loads)

        pm_res = self.generate_pm_diagram(num_points=30)
        pu = loads.Pu
        mu = abs(loads.Mu)

        if not pm_res.phi_points:
            return InteractionResult(
                axial_ratio=0.0,
                flexure_ratio=0.0,
                demand_capacity_ratio=0.0,
                status="Failed",
                messages=["Could not generate P-M interaction diagram."],
            )

        # Interpolate capacity curve for given Pu to get maximum phi*Mn
        capacity_mu = 0.0
        for i in range(len(pm_res.phi_points) - 1):
            m1, p1 = pm_res.phi_points[i]
            m2, p2 = pm_res.phi_points[i + 1]

            if (p1 >= pu >= p2) or (p2 >= pu >= p1):
                if abs(p2 - p1) > 1e-3:
                    frac = (pu - p1) / (p2 - p1)
                    capacity_mu = m1 + frac * (m2 - m1)
                else:
                    capacity_mu = max(m1, m2)
                break

        dcr = mu / capacity_mu if capacity_mu > 0.0 else (1.5 if mu > 0 else 0.0)
        status = "Passed"
        messages = []

        if dcr > 1.0:
            status = "Failed"
            messages.append(f"P-M Interaction demand/capacity ratio {dcr:.2f} exceeds 1.0.")
        elif dcr > 0.9:
            status = "Warning"
            messages.append(f"P-M Interaction demand/capacity ratio {dcr:.2f} is near capacity.")

        return InteractionResult(
            axial_ratio=pu / max(pm_res.phi_points[0][1], 1.0) if pm_res.phi_points else 0.0,
            flexure_ratio=mu / max(capacity_mu, 1.0),
            demand_capacity_ratio=dcr,
            status=status,
            messages=messages,
        )
