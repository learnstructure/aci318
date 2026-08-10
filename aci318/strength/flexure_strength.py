import math
from aci318.loads.load_effects import LoadEffects
from aci318.results.flexure import FlexureResult
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class FlexureStrength(StrengthChecker):
    """
    Modular flexural strength checker according to ACI 318-19 §22.2.
    
    Equations:
        Equivalent Rectangular Stress Block (ACI 318-19 §22.2.2.4):
            a = beta_1 * c
            Cc = 0.85 * f'c * a * b_eff  (for a <= h_f)
            Cc = 0.85 * f'c * [a * b_w + h_f * (b_f - b_w)]  (for a > h_f in T-sections)
            
        Strain Compatibility (ACI 318-19 §22.2.1):
            epsilon_s_i = epsilon_cu * (d_i - c) / c
            f_s_i = min(max(Es * epsilon_s_i, -fy), fy)
            
        Internal Equilibrium:
            Sum(C) = Sum(T) => Cc + Sum(Cs_i) = Sum(Ts_i)
            
        Nominal Bending Strength Mn:
            Mn = Cc * (d - y_c) + Sum(A_s_i * f_s_i * (d - d_i))
            phi_Mn = phi * Mn
    """

    def check(self, loads: LoadEffects) -> FlexureResult:
        """
        Perform flexural strength evaluation for given load effects.
        
        Args:
            loads: LoadEffects instance containing Mu (kip-in).
            
        Returns:
            FlexureResult dataclass.
        """
        validate_load_effects(loads)

        fc = self.section.concrete.fc
        beta_1 = self.code.get_beta_1(fc)
        epsilon_cu = getattr(self.section.concrete, "max_strain", 0.003)

        b = getattr(self.section, "b_f", getattr(self.section, "b", 12.0))
        bw = getattr(self.section, "b_w", b)
        hf = getattr(self.section, "h_f", 0.0)
        h = self.section.h

        As, d = self.section.tension_steel
        if As <= 0.0 or d <= 0.0:
            return FlexureResult(
                required_steel=0.0,
                provided_steel=0.0,
                neutral_axis=0.0,
                steel_strain=0.0,
                phi_mn=0.0,
                status="Failed",
                messages=["No tension steel provided in section."],
                demand_capacity_ratio=0.0,
            )

        fy = self.section.layers[-1].steel.fy if self.section.layers else 60.0
        Es = self.section.layers[-1].steel.Es if self.section.layers else 29000.0
        epsilon_ty = fy / Es

        # Iterative or analytical solution for neutral axis depth c using strain compatibility
        # Objective function: F(c) = Concrete_compression + Steel_compression - Steel_tension = 0
        def force_equilibrium(c_trial: float) -> float:
            if c_trial <= 0.001:
                return -1e6
            a_trial = beta_1 * c_trial
            if hf > 0.0 and a_trial > hf:
                cc = 0.85 * fc * (a_trial * bw + hf * (b - bw))
            else:
                cc = 0.85 * fc * a_trial * b

            cs_and_ts = 0.0
            for layer in self.section.layers:
                eps_i = epsilon_cu * (layer.depth - c_trial) / c_trial
                fs_i = max(min(layer.steel.Es * eps_i, layer.steel.fy), -layer.steel.fy)
                if eps_i < 0:  # Compression
                    # Subtract displaced concrete force
                    cs_and_ts += layer.area * (abs(fs_i) - 0.85 * fc)
                else:  # Tension
                    cs_and_ts -= layer.area * fs_i

            return cc + cs_and_ts

        # Bisection to solve for neutral axis c
        c_low = 0.01
        c_high = h * 1.5
        c = (c_low + c_high) / 2.0

        for _ in range(50):
            c = (c_low + c_high) / 2.0
            f_val = force_equilibrium(c)
            if abs(f_val) < 1e-4:
                break
            if f_val > 0:
                c_high = c
            else:
                c_low = c

        a = beta_1 * c
        strain_t = epsilon_cu * (d - c) / c

        # Compute nominal moment Mn about centroid of tension steel or section centroid
        if hf > 0.0 and a > hf:
            c1 = 0.85 * fc * a * bw
            y1 = a / 2.0
            c2 = 0.85 * fc * hf * (b - bw)
            y2 = hf / 2.0
            mn_conc = c1 * (d - y1) + c2 * (d - y2)
        else:
            cc = 0.85 * fc * a * b
            mn_conc = cc * (d - a / 2.0)

        mn_steel = 0.0
        for layer in self.section.layers:
            if layer.depth < c:  # Compression steel
                eps_i = epsilon_cu * (c - layer.depth) / c
                fs_i = min(layer.steel.Es * eps_i, layer.steel.fy)
                mn_steel += layer.area * (fs_i - 0.85 * fc) * (d - layer.depth)

        mn = mn_conc + mn_steel
        phi = self.code.get_phi_flexure(strain_t)
        phi_mn = phi * mn

        status = "Passed"
        messages = []
        min_steel_ratio = self.code.get_minimum_steel_ratio(fc, fy)
        min_As = min_steel_ratio * bw * d

        if As < min_As:
            status = "Warning"
            messages.append(f"Tension steel As ({As:.3f} in^2) is less than ACI minimum As_min ({min_As:.3f} in^2).")
        if strain_t < 0.004:
            status = "Warning"
            messages.append(f"Net tensile strain strain_t ({strain_t:.5f}) is less than 0.004 (ductility warning).")

        demand = max(loads.Mu, 0.0)
        capacity = max(phi_mn, 0.0)
        ratio = demand / capacity if capacity > 0.0 else 0.0

        if ratio > 1.0:
            status = "Failed"
            messages.append(f"Demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        elif ratio > 0.9:
            status = "Warning"
            messages.append(f"Demand/capacity ratio {ratio:.2f} is near capacity.")

        return FlexureResult(
            required_steel=min_As,
            provided_steel=As,
            neutral_axis=c,
            steel_strain=strain_t,
            phi_mn=phi_mn,
            status=status,
            messages=messages,
            demand_capacity_ratio=ratio,
        )
