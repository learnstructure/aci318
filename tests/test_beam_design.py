import unittest
from aci318.codes.aci318_19 import ACI318_19
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.members.beam import Beam
from aci318.sections.rectangle import RectangleSection


class TestBeamDesign(unittest.TestCase):
    def test_beam_flexural_and_shear_check(self):
        concrete = Concrete(fc=4.0)
        steel = Steel(fy=60.0)
        section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
        section.add_rebar_layer(area=2.37, depth=21.5, steel=steel)
        code = ACI318_19()

        beam = Beam(section=section, code=code)
        loads = LoadEffects(Pu=0.0, Mu=2500.0, Vu=30.0, Tu=0.0)
        result = beam.check(loads)

        self.assertIn(result.status, ("Passed", "Warning"))
        self.assertEqual(result.flexure.provided_steel, 2.37)
        self.assertGreater(result.flexure.phi_mn, 0.0)
        self.assertGreater(result.shear.vn_concrete, 0.0)
        self.assertGreater(result.shear.phi_vn, 0.0)

        self.assertAlmostEqual(result.flexure.neutral_axis, 4.10, delta=0.5)
        self.assertAlmostEqual(result.flexure.steel_strain, 0.0127, delta=0.005)
        self.assertAlmostEqual(result.flexure.phi_mn, 2528.5, delta=100.0)

    def test_beam_automatic_design(self):
        concrete = Concrete(fc=4.0)
        code = ACI318_19()
        section = RectangleSection(b=12.0, h=24.0, concrete=concrete)

        beam = Beam(
            section=section,
            code=code,
            stirrup_bar_size="#3",
            stirrup_spacing=12.0,
            stirrup_legs=2,
            fy_shear=60.0,
        )

        loads = LoadEffects(Pu=0.0, Mu=2500.0, Vu=30.0, Tu=0.0)
        design_result = beam.design(loads, fy_flexure=60.0)

        self.assertIn(design_result.status, ("Passed", "Warning"))
        self.assertGreater(design_result.required_flexure_As, 0.0)
        self.assertNotIn("None", design_result.suggested_bars)
        self.assertGreaterEqual(design_result.provided_flexure_As, design_result.required_flexure_As)
        self.assertGreater(design_result.required_shear_spacing, 0.0)


if __name__ == "__main__":
    unittest.main()
