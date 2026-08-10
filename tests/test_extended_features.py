import unittest
from aci318.codes import ACI318_19, ACI318_25
from aci318.foundations import IsolatedFooting
from aci318.loads import LoadEffects
from aci318.materials import Concrete, Steel
from aci318.members import Beam, Column, Slab, Wall
from aci318.optimization import BeamSectionOptimizer
from aci318.reports import BeamTextReport, MarkdownReport
from aci318.sections import CircularSection, RectangleSection, TBeamSection
from aci318.strength import TorsionStrength, calculate_development_length, design_splice


class TestExtendedFeatures(unittest.TestCase):
    def setUp(self):
        self.code19 = ACI318_19()
        self.code25 = ACI318_25()
        self.concrete = Concrete(fc=4.0)
        self.steel = Steel(fy=60.0)

    def test_tbeam_section(self):
        t_sec = TBeamSection(b_f=36.0, h_f=5.0, b_w=12.0, h=24.0, concrete=self.concrete)
        t_sec.add_rebar_layer(area=3.0, depth=21.5, steel=self.steel)
        self.assertGreater(t_sec.gross_area, 0.0)
        self.assertGreater(t_sec.centroid, 0.0)
        self.assertGreater(t_sec.gross_inertia, 0.0)

        beam = Beam(section=t_sec, code=self.code19)
        res = beam.check(LoadEffects(Mu=2000.0, Vu=25.0))
        self.assertIn(res.status, ("Passed", "Warning"))

    def test_circular_section(self):
        circ_sec = CircularSection(D=20.0, concrete=self.concrete)
        circ_sec.setup_circular_bar_pattern(num_bars=8, bar_size="#8", steel=self.steel)
        self.assertAlmostEqual(circ_sec.gross_area, 314.159, delta=1.0)

        col = Column(section=circ_sec, code=self.code19, spiral=True)
        res = col.design(LoadEffects(Pu=200.0, Mu=500.0, Vu=30.0))
        self.assertIn(res.status, ("Passed", "Warning"))

    def test_torsion_strength_engine(self):
        sec = RectangleSection(b=12.0, h=24.0, concrete=self.concrete)
        sec.add_rebar_layer(area=2.37, depth=21.5, steel=self.steel)

        torsion_checker = TorsionStrength(sec, self.code19)
        res = torsion_checker.check(LoadEffects(Tu=100.0, Vu=30.0))
        self.assertGreater(res.threshold_torsion, 0.0)
        self.assertGreater(res.cracking_torsion, 0.0)

    def test_slab_design(self):
        slab = Slab(thickness=6.0, concrete=self.concrete, code=self.code19)
        res = slab.design(LoadEffects(Mu=60.0, Vu=5.0))  # in kip-in/ft and kip/ft
        self.assertIn(res.status, ("Passed", "Warning"))
        self.assertGreater(res.provided_flexure_As, 0.0)

    def test_wall_design(self):
        wall = Wall(thickness=10.0, height=120.0, length=240.0, concrete=self.concrete, code=self.code19)
        res = wall.design(LoadEffects(Pu=20.0, Mu=100.0, Vu=10.0))
        self.assertIn(res.status, ("Passed", "Warning"))

    def test_isolated_footing(self):
        ftg = IsolatedFooting(
            length=8.0,
            width=8.0,
            thickness=18.0,
            col_c1=18.0,
            col_c2=18.0,
            concrete=self.concrete,
            steel=self.steel,
            code=self.code19,
        )
        res = ftg.design(LoadEffects(Pu=150.0, Mu=200.0, Vu=15.0))
        self.assertIn(res.status, ("Passed", "Warning"))

    def test_section_optimizer(self):
        optimizer = BeamSectionOptimizer(code=self.code19, fc=4.0, fy=60.0)
        opt_res = optimizer.optimize(
            loads=LoadEffects(Mu=1800.0, Vu=25.0),
            min_b=12.0, max_b=16.0, step_b=2.0,
            min_h=20.0, max_h=24.0, step_h=2.0,
        )
        self.assertGreater(opt_res.width, 0.0)
        self.assertGreater(opt_res.height, 0.0)
        self.assertGreater(opt_res.cost_per_ft, 0.0)

    def test_development_and_splices(self):
        dev_res = calculate_development_length(
            bar_diameter=1.0, steel=self.steel, concrete=self.concrete, code=self.code19
        )
        self.assertGreater(dev_res.ld_tension, 12.0)

        splice_res = design_splice(
            bar_size="#8", steel=self.steel, concrete=self.concrete, code=self.code19, splice_class="B"
        )
        self.assertGreater(splice_res.splice_length, 12.0)

    def test_reports(self):
        sec = RectangleSection(b=12.0, h=24.0, concrete=self.concrete)
        sec.add_rebar_layer(area=2.37, depth=21.5, steel=self.steel)
        beam = Beam(section=sec, code=self.code19)
        loads = LoadEffects(Mu=2000.0, Vu=25.0)
        check_res = beam.check(loads)

        txt_report = BeamTextReport(section=sec, loads=loads, result=check_res)
        txt_output = txt_report.generate()
        self.assertIn("RECTANGULAR BEAM DESIGN", txt_output)

        md_report = MarkdownReport(title="Beam Calculation Report", section=sec, loads=loads, result=check_res)
        md_output = md_report.generate()
        self.assertIn("# Beam Calculation Report", md_output)


if __name__ == "__main__":
    unittest.main()
