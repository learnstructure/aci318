import unittest
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel


class TestMaterials(unittest.TestCase):
    def test_concrete_creation(self):
        concrete = Concrete(fc=4.0)
        self.assertEqual(concrete.fc, 4.0)
        self.assertEqual(concrete.density, 145.0)
        self.assertEqual(concrete.concrete_type, "normalweight")
        self.assertEqual(concrete.max_strain, 0.003)
        self.assertAlmostEqual(concrete.Ec, 3604.996, delta=0.1)

    def test_steel_creation(self):
        steel = Steel(fy=60.0)
        self.assertEqual(steel.fy, 60.0)
        self.assertEqual(steel.Es, 29000.0)
        self.assertAlmostEqual(steel.yield_strain, 60.0 / 29000.0, places=5)


if __name__ == "__main__":
    unittest.main()
