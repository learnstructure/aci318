"""
Markdown engineering design report generator.
"""

from typing import Any, Union
from aci318.loads.load_effects import LoadEffects
from aci318.reports.base import ReportBase
from aci318.results.beam import BeamCheckResult, BeamDesignResult


class MarkdownReport(ReportBase):
    """
    Generates a structured Markdown design calculation report suitable for documentation or conversion to PDF/HTML.
    """

    def __init__(
        self,
        title: str,
        section: Any,
        loads: LoadEffects,
        result: Any,
        code_name: str = "ACI 318-19",
    ) -> None:
        self.title = title
        self.section = section
        self.loads = loads
        self.result = result
        self.code_name = code_name

    def generate(self) -> str:
        lines = [
            f"# {self.title}",
            f"**Design Code:** {self.code_name}  ",
            "---",
            "",
            "## 1. Input Parameters",
            "### Section Properties",
            f"- **Width (b):** {getattr(self.section, 'b', 0.0):.2f} in",
            f"- **Height (h):** {getattr(self.section, 'h', 0.0):.2f} in",
            f"- **Gross Area (Ag):** {getattr(self.section, 'gross_area', 0.0):.2f} in²",
            f"- **Gross Inertia (Ig):** {getattr(self.section, 'gross_inertia', 0.0):,.0f} in⁴",
            "",
            "### Material Properties",
            f"- **Concrete Compressive Strength (f'c):** {self.section.concrete.fc:.2f} ksi",
            f"- **Concrete Elastic Modulus (Ec):** {self.section.concrete.Ec:.0f} ksi",
            "",
            "### Factored Loads",
            f"- **Factored Bending Moment (Mu):** {self.loads.Mu:.1f} kip-in",
            f"- **Factored Shear Force (Vu):** {self.loads.Vu:.1f} kip",
        ]

        if self.loads.Tu:
            lines.append(f"- **Factored Torsion (Tu):** {self.loads.Tu:.1f} kip-in")
        if self.loads.Pu:
            lines.append(f"- **Factored Axial Load (Pu):** {self.loads.Pu:.1f} kip")

        lines.extend([
            "",
            "## 2. Design Results & Checks",
            f"**Overall Status:** `{self.result.status}`",
            "",
        ])

        if hasattr(self.result, "required_flexure_As"):
            lines.extend([
                "### Flexural Steel Design",
                f"- **Required Steel Area (As,req):** {self.result.required_flexure_As:.3f} in²",
                f"- **Provided Steel Area (As,prov):** {self.result.provided_flexure_As:.3f} in²",
                f"- **Suggested Layout:** `{self.result.suggested_bars}`",
                "",
                "### Shear Reinforcement Design",
                f"- **Stirrup Bar Size:** {self.result.stirrup_bar_size}",
                f"- **Stirrup Legs:** {self.result.stirrup_legs}",
                f"- **Required Spacing:** {self.result.required_shear_spacing:.1f} in",
            ])

        if hasattr(self.result, "messages") and self.result.messages:
            lines.extend(["", "### Notes & Warnings"])
            for msg in self.result.messages:
                lines.append(f"- {msg}")

        return "\n".join(lines)
