import math
from aci318.loads.load_effects import LoadEffects
from aci318.results.shear import ShearResult
from aci318.strength.base import StrengthChecker
from aci318.validators.loads import validate_load_effects


class ShearStrength(StrengthChecker):
    """
    Modular shear strength checker for reinforced concrete members (ACI 318-19 §22.5 & §9.6.3).
    
    Equations:
        Nominal Shear Capacity Vn:
            Vn = Vc + Vs
            phi_Vn = phi_v * Vn  (phi_v = 0.75)
            
        Concrete Shear Capacity Vc (ACI 318-19 Table 22.5.5.1):
            Vc = [2 * lambda * sqrt(f'c) + Nu / (6 * Ag)] * bw * d / 1000
            
        Stirrup Shear Capacity Vs (ACI 318-19 §22.5.8.5.3):
            Vs = (Av * fyt * d) / s
            Vs_max = 8 * sqrt(f'c) * bw * d / 1000
    """

    def __init__(self, section, code, av: float = 0.0, s: float = 0.0, fy_shear: float = None) -> None:
        super().__init__(section, code)
        self.av = av
        self.s = s
        if fy_shear is None:
            fy_val = getattr(getattr(self.section, "transverse_steel", None), "fy", None)
            if fy_val is None:
                fy_val = getattr(getattr(self.section, "steel", None), "fy", None)
            if fy_val is None and getattr(self.section, "layers", None):
                for lyr in self.section.layers:
                    if getattr(lyr, "steel", None) and getattr(lyr.steel, "fy", None):
                        fy_val = lyr.steel.fy
                        break
            if fy_val is None:
                if av > 0.0:
                    raise ValueError("Shear reinforcement yield strength fy_shear must be specified when av > 0.")
                fy_val = 60.0
            fy_shear = fy_val
        # Stirrups, ties, and hoops for shear: fyt limited to 60 ksi (Table 20.2.2.4(a))
        self.fy_shear = min(fy_shear, 60.0)

    def check(self, loads: LoadEffects) -> ShearResult:
        """
        Perform shear strength check for given load effects.
        
        Args:
            loads: LoadEffects instance containing Vu (kip), Pu (kip).
            
        Returns:
            ShearResult dataclass.
        """
        validate_load_effects(loads)

        bw = getattr(self.section, "b_w", getattr(self.section, "b", None))
        if bw is None or bw <= 0.0:
            raise ValueError(f"Section width bw must be defined and positive, got {bw!r}")
        h = self.section.h
        fc = self.section.concrete.fc
        fc_psi = fc * 1000.0

        As, d = self.section.tension_steel
        if d <= 0.0:  # before bars are placed: inside the cover, a stirrup and half a bar (1.0 in)
            d = max(h - self.section.cover - 1.0, 1.0)

        if (bw * d) <= 0.0:
            raise ValueError(f"Section effective shear area (bw * d) must be positive, got bw={bw}, d={d}")
        rho_w = As / (bw * d)
        Ag = getattr(self.section, "gross_area", bw * h)
        lambda_val = self.code.get_lambda_(self.section.concrete)

        # Minimum shear steel area requirement (ACI 318-19 §9.6.3.3)
        denom = max(self.fy_shear * 1000.0, 1.0)
        av_min_per_in = max(0.75 * math.sqrt(fc_psi), 50.0) * bw / denom
        av_min = av_min_per_in * self.s if self.s > 0 else 0.0

        Vc = self.code.get_vc(
            f_c=fc,
            b_w=bw,
            d=d,
            N_u=loads.Pu,
            A_g=Ag,
            A_v=self.av,
            A_v_min=av_min,
            lambda_val=lambda_val,
            rho_w=rho_w,
        )

        if self.s > 0.0 and self.av > 0.0:
            Vs = (self.av * self.fy_shear * d) / self.s
        else:
            Vs = 0.0

        vs_max = (8.0 * math.sqrt(fc_psi) * bw * d) / 1000.0
        status = "Passed"
        messages = []

        if Vs > vs_max:
            status = "Failed"
            messages.append(f"Stirrup shear strength Vs ({Vs:.2f} kip) exceeds maximum allowed Vs_max ({vs_max:.2f} kip).")

        vn = Vc + Vs
        phi_v = self.code.get_phi_shear()
        phi_vn = phi_v * vn

        demand = max(abs(loads.Vu), 0.0)
        capacity = max(phi_vn, 0.0)
        ratio = demand / capacity if capacity > 0.0 else 0.0

        if ratio > 1.0:
            status = "Failed"
            messages.append(f"Shear demand/capacity ratio {ratio:.2f} exceeds 1.0.")
        elif ratio > 0.9:
            status = "Warning"
            messages.append(f"Shear demand/capacity ratio {ratio:.2f} is near capacity.")

        return ShearResult(
            vn_concrete=Vc,
            vn_steel=Vs,
            phi_vn=phi_vn,
            required_spacing=self.s,
            status=status,
            messages=messages,
            demand_capacity_ratio=ratio,
        )
