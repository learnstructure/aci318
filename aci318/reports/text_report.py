"""
Plain-text (ASCII) report generator for beam design results.
"""

from aci318.loads.load_effects import LoadEffects
from aci318.reports.base import ReportBase
from aci318.results.beam import BeamDesignResult
from aci318.sections.rectangle import RectangleSection


class BeamTextReport(ReportBase):
    """
    Generates a plain-text engineering design report for a rectangular beam.

    Example usage::

        from aci318.reports.text_report import BeamTextReport
        report = BeamTextReport(section, loads, result, code_name="ACI 318-19")
        report.print_to_console()
        report.save("output/beam_report.txt")
    """

    def __init__(
        self,
        section: RectangleSection,
        loads: LoadEffects,
        result: BeamDesignResult,
        code_name: str = "ACI 318-19",
        title: str = "RECTANGULAR BEAM DESIGN",
    ) -> None:
        self.section   = section
        self.loads     = loads
        self.result    = result
        self.code_name = code_name
        self.title     = title

    # ── private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _ok(capacity: float, demand: float) -> str:
        return "OK" if capacity >= demand else "NG"

    @staticmethod
    def _dcr(demand: float, capacity: float) -> float:
        return demand / capacity if capacity else float("inf")

    @staticmethod
    def _sep(char: str = "=", width: int = 62) -> str:
        return char * width

    # ── public ────────────────────────────────────────────────────────────────

    def generate(self) -> str:
        s  = self.section
        lo = self.loads
        r  = self.result
        fl = r.flexure
        sh = r.shear

        concrete = s.concrete
        steel    = s.layers[-1].steel if s.layers else None
        As, d    = s.tension_steel

        lines = [
            self._sep(),
            f"  {self.title}  |  {self.code_name}",
            self._sep(),
            "",
            "SECTION PROPERTIES",
            self._sep("-"),
            f"  b  (width)              = {s.b:.2f} in",
            f"  h  (height)             = {s.h:.2f} in",
            f"  d  (effective depth)    = {d:.2f} in",
            f"  Ag (gross area)         = {s.gross_area:.2f} in²",
            f"  Ig (gross inertia)      = {s.gross_inertia:,.0f} in⁴",
            f"  As (tension steel)      = {As:.3f} in²",
            "",
            "MATERIAL PROPERTIES",
            self._sep("-"),
            f"  f'c                     = {concrete.fc:.2f} ksi  ({concrete.fc*1000:.0f} psi)",
            f"  Ec                      = {concrete.Ec:.0f} ksi",
        ]
        if steel:
            lines += [
                f"  fy                      = {steel.fy:.0f} ksi",
                f"  Es                      = {steel.Es:.0f} ksi",
            ]
        lines += [
            "",
            "LOAD EFFECTS (FACTORED)",
            self._sep("-"),
            f"  Mu                      = {lo.Mu:.1f} kip-in",
            f"  Vu                      = {lo.Vu:.1f} kip",
        ]
        if lo.Tu:
            lines.append(f"  Tu                      = {lo.Tu:.1f} kip-in")
        if lo.Pu:
            lines.append(f"  Pu                      = {lo.Pu:.1f} kip")

        lines += [
            "",
            "FLEXURE  (ACI 318 Ch. 22)",
            self._sep("-"),
            f"  Neutral axis c          = {fl.neutral_axis:.3f} in",
            f"  Net tensile strain εt   = {fl.steel_strain:.5f}",
            f"  Min. steel As,min       = {fl.required_steel:.3f} in²",
            f"  Provided steel As       = {fl.provided_steel:.3f} in²",
            f"  φ·Mn                    = {fl.phi_mn:.1f} kip-in",
            f"  Mu                      = {lo.Mu:.1f} kip-in",
            f"  DCR (Mu/φMn)            = {self._dcr(lo.Mu, fl.phi_mn):.3f}",
            f"  Status                  = {self._ok(fl.phi_mn, lo.Mu)}",
        ]
        if fl.messages:
            lines.append("  Warnings:")
            for msg in fl.messages:
                lines.append(f"    ! {msg}")

        lines += [
            "",
            "SHEAR  (ACI 318 Ch. 22)",
            self._sep("-"),
            f"  Vc (concrete)           = {sh.vn_concrete:.2f} kip",
            f"  Vs (stirrups)           = {sh.vn_steel:.2f} kip",
            f"  φ·Vn                    = {sh.phi_vn:.2f} kip",
            f"  Vu                      = {lo.Vu:.1f} kip",
            f"  DCR (Vu/φVn)            = {self._dcr(lo.Vu, sh.phi_vn):.3f}",
            f"  Status                  = {self._ok(sh.phi_vn, lo.Vu)}",
        ]
        if sh.messages:
            lines.append("  Warnings:")
            for msg in sh.messages:
                lines.append(f"    ! {msg}")

        lines += [
            "",
            self._sep(),
            f"  OVERALL STATUS  →  {r.status}",
            self._sep(),
        ]
        if r.messages:
            for msg in r.messages:
                lines.append(f"  ! {msg}")

        return "\n".join(lines)
