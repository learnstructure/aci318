import copy
from typing import Optional, Sequence, Union

from aci318.codes.base import DesignCode
from aci318.database.bars import Rebar
from aci318.detailing.column import create_column_detail
from aci318.loads.load_effects import LoadEffects
from aci318.results.column import ColumnDesignResult
from aci318.sections.circle import CircularSection
from aci318.sections.rectangle import RectangleSection
from aci318.strength.axial_strength import AxialStrength
from aci318.strength.interaction_strength import InteractionStrength
from aci318.strength.shear_strength import ShearStrength
from aci318.validators.loads import validate_load_effects


class Column:
    """
    User-facing Column class coordinating column design calculations according to ACI 318-19 Chapter 10.
    """

    def __init__(
        self,
        section: Union[RectangleSection, CircularSection],
        code: DesignCode,
        member_id: str = "column-01",
        tie_bar_size: str = "#3",
        tie_spacing: float = 12.0,
        spiral: bool = False,
        required_steel: Optional[float] = None,
        fy_shear: float = 60.0,
    ) -> None:
        """``required_steel`` is the longitudinal area the design calls for (in^2); by default the
        §10.6.1.1 minimum of 0.01 Ag. ``fy_shear`` is the yield strength of the ties (ksi), limited to 60 ksi for
        shear (Table 20.2.2.4(a))."""
        self.section = section
        self.code = code
        self.member_id = member_id
        self.tie_bar_size = tie_bar_size
        self.tie_spacing = tie_spacing
        self.spiral = spiral
        self.required_steel = 0.01 * section.gross_area if required_steel is None else required_steel
        self.fy_shear = min(fy_shear, 60.0)

    def check(self, loads: Union[LoadEffects, Sequence[LoadEffects]]) -> ColumnDesignResult:
        """
        Evaluate structural capacity and demand-capacity ratios for given loads.

        Args:
            loads: One LoadEffects object, or a sequence of concurrent load sets (see ``design``).

        Returns:
            ColumnDesignResult dataclass.
        """
        return self.design(loads)

    def design(self, loads: Union[LoadEffects, Sequence[LoadEffects]]) -> ColumnDesignResult:
        """
        Coordinates axial, P-M interaction, and shear checks for the column member.

        Args:
            loads: One LoadEffects object (Pu in kip, compression positive; Mu in kip-in; Vu in kip),
                or a sequence of concurrent load sets, e.g. one per load combination and station.
                Each set is checked on its own and the governing ratios are reported.

        Returns:
            ColumnDesignResult dataclass.
        """
        load_sets = [loads] if isinstance(loads, LoadEffects) else list(loads)
        if not load_sets:
            raise ValueError("Column.design requires at least one load set.")
        for item in load_sets:
            validate_load_effects(item)

        axial_checker = AxialStrength(self.section, self.code, spiral=self.spiral)
        axial_res = axial_checker.check(max(load_sets, key=lambda item: item.Pu))

        interaction_checker = InteractionStrength(self.section, self.code, spiral=self.spiral)
        interaction_res = interaction_checker.check_load_sets(load_sets)

        av = 2 * Rebar(bar_size=self.tie_bar_size).area
        shear_checker = ShearStrength(self.section, self.code, av=av, s=self.tie_spacing, fy_shear=self.fy_shear)
        shear_res = max(
            (shear_checker.check(item) for item in load_sets), key=lambda r: r.demand_capacity_ratio
        )

        from aci318.results.flexure import FlexureResult

        provided_ast = sum(layer.area for layer in self.section.layers) if self.section.layers else 0.0
        flexure_mapped = FlexureResult(
            required_steel=self.required_steel,
            provided_steel=provided_ast,
            neutral_axis=self.section.h / 2.0 if hasattr(self.section, "h") else 0.0,
            steel_strain=0.005,
            phi_mn=max(axial_res.phi_pn_max, 0.0),
            status=axial_res.status,
            messages=axial_res.messages + interaction_res.messages,
            demand_capacity_ratio=max(axial_res.demand_capacity_ratio, interaction_res.demand_capacity_ratio),
        )

        status = "Passed"
        if axial_res.status == "Failed" or shear_res.status == "Failed" or interaction_res.status == "Failed":
            status = "Failed"
        elif axial_res.status == "Warning" or shear_res.status == "Warning" or interaction_res.status == "Warning":
            status = "Warning"

        messages = list(set(axial_res.messages + interaction_res.messages + shear_res.messages))

        from aci318.detailing.base import BarPlacement

        bar_placements = [
            BarPlacement(
                id=f"{self.member_id}-long-layer-{i}",
                bar_size=lyr.bar_size or "#8",
                count=lyr.num_bars or 1,
                location="longitudinal",
                cover=self.section.cover,
            )
            for i, lyr in enumerate(self.section.layers)
        ]
        tie_placements = [
            BarPlacement(
                id=f"{self.member_id}-tie-1",
                bar_size=self.tie_bar_size,
                count=1,
                location="tie" if not self.spiral else "spiral",
                spacing=self.tie_spacing,
                cover=self.section.cover,
            )
        ]
        detailing_obj = create_column_detail(
            member_id=self.member_id,
            longitudinal_bars=bar_placements,
            ties=tie_placements,
        )

        return ColumnDesignResult(
            axial_flexure=flexure_mapped,
            shear=shear_res,
            status=status,
            messages=messages,
            pm_interaction=interaction_res,
            detailing=detailing_obj,
        )
