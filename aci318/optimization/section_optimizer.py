import math
from dataclasses import dataclass
from typing import List, Optional

from aci318.codes.base import DesignCode
from aci318.codes.aci318_19 import ACI318_19
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.beam import Beam
from aci318.results.beam import BeamDesignResult
from aci318.sections.rectangle import RectangleSection


@dataclass
class OptimalBeamResult:
    """Dataclass holding output from section optimization."""
    width: float                      # Optimal width b (in)
    height: float                     # Optimal height h (in)
    cost_per_ft: float                # Total material cost ($/ft)
    concrete_cost_per_ft: float       # Concrete cost ($/ft)
    steel_cost_per_ft: float          # Steel cost ($/ft)
    design_result: BeamDesignResult   # Design result object
    section: RectangleSection         # Optimized section object
    feasible: bool = True             # Whether design satisfies all code constraints


class BeamSectionOptimizer:
    """
    Optimizes beam cross-sectional dimensions (b, h) to minimize material cost ($/ft) or carbon footprint.
    """

    def __init__(
        self,
        code: Optional[DesignCode] = None,
        fc: float = 4.0,
        fy: float = 60.0,
        concrete_cost_yd3: float = 150.0,  # $/yd^3
        steel_cost_lb: float = 1.25,        # $/lb
    ) -> None:
        self.code = code or ACI318_19()
        self.concrete = Concrete(fc=fc)
        self.steel = Steel(fy=fy)
        self.concrete_cost_yd3 = concrete_cost_yd3
        self.steel_cost_lb = steel_cost_lb

    def optimize(
        self,
        loads: LoadEffects,
        min_b: float = 10.0,
        max_b: float = 24.0,
        step_b: float = 2.0,
        min_h: float = 12.0,
        max_h: float = 36.0,
        step_h: float = 2.0,
        raise_on_failure: bool = True,
    ) -> OptimalBeamResult:
        """
        Search grid of section sizes to find minimum material cost design that satisfies ACI 318.
        
        Args:
            loads: Factored load effects.
            min_b, max_b, step_b: Width range in inches.
            min_h, max_h, step_h: Height range in inches.
            raise_on_failure: If True (default), raises ValueError when no section meets constraints.
                If False, returns a non-feasible result with feasible=False.
            
        Returns:
            OptimalBeamResult dataclass.
            
        Raises:
            ValueError: If no candidate section satisfies constraints and raise_on_failure is True.
        """
        best_result: Optional[OptimalBeamResult] = None
        min_cost = float("inf")

        b_val = min_b
        while b_val <= max_b:
            h_val = min_h
            while h_val <= max_h:
                section = RectangleSection(b=b_val, h=h_val, concrete=self.concrete)
                beam = Beam(section=section, code=self.code)
                design_res = beam.design(loads, fy_flexure=self.steel.fy)

                if design_res.status != "Failed" and design_res.provided_flexure_As > 0:
                    # Calculate concrete volume and cost per foot
                    vol_ft3_conc = (b_val * h_val) / 144.0
                    vol_yd3_conc = vol_ft3_conc / 27.0
                    c_cost = vol_yd3_conc * self.concrete_cost_yd3

                    # Calculate steel weight and cost per foot (steel density = 490 lb/ft^3)
                    as_total = design_res.provided_flexure_As
                    if design_res.required_shear_spacing > 0:
                        # Add stirrup weight estimate per foot
                        stirrup_perimeter_ft = (2.0 * b_val + 2.0 * h_val) / 12.0
                        as_stirrup_per_ft = (12.0 / design_res.required_shear_spacing) * 0.22  # #3 stirrups
                        as_total += as_stirrup_per_ft

                    vol_ft3_steel = as_total / 144.0
                    weight_lb_steel = vol_ft3_steel * 490.0
                    s_cost = weight_lb_steel * self.steel_cost_lb

                    total_cost = c_cost + s_cost

                    if total_cost < min_cost:
                        min_cost = total_cost
                        best_result = OptimalBeamResult(
                            width=b_val,
                            height=h_val,
                            cost_per_ft=total_cost,
                            concrete_cost_per_ft=c_cost,
                            steel_cost_per_ft=s_cost,
                            design_result=design_res,
                            section=section,
                            feasible=True,
                        )

                h_val += step_h
            b_val += step_b

        if best_result is None:
            if raise_on_failure:
                raise ValueError(
                    f"No feasible beam section found satisfying ACI 318 design constraints within "
                    f"width [{min_b}, {max_b}] in and height [{min_h}, {max_h}] in for loads "
                    f"Pu={loads.Pu}, Mu={loads.Mu}, Vu={loads.Vu}."
                )
            fallback_sec = RectangleSection(b=max_b, h=max_h, concrete=self.concrete)
            fallback_beam = Beam(section=fallback_sec, code=self.code)
            fallback_res = fallback_beam.design(loads)
            return OptimalBeamResult(
                width=max_b,
                height=max_h,
                cost_per_ft=0.0,
                concrete_cost_per_ft=0.0,
                steel_cost_per_ft=0.0,
                design_result=fallback_res,
                section=fallback_sec,
                feasible=False,
            )

        return best_result
