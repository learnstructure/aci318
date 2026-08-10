import unittest
from aci318.utils.units import (
    convert_force, 
    convert_length, 
    convert_stress, 
    convert_moment,
    IN_TO_MM,
    MM_TO_IN
)


class TestUnits(unittest.TestCase):
    def test_length_conversion(self):
        self.assertAlmostEqual(convert_length(1.0, "in", "mm"), 25.4, places=2)
        self.assertAlmostEqual(convert_length(25.4, "mm", "in"), 1.0, places=2)
        self.assertAlmostEqual(convert_length(1.0, "ft", "in"), 12.0, places=2)
        self.assertAlmostEqual(convert_length(12.0, "in", "ft"), 1.0, places=2)

    def test_force_conversion(self):
        self.assertAlmostEqual(convert_force(1.0, "kip", "lb"), 1000.0, places=2)
        self.assertAlmostEqual(convert_force(1000.0, "lb", "kip"), 1.0, places=2)
        self.assertAlmostEqual(convert_force(1.0, "kip", "kn"), 4.44822, delta=1e-3)

    def test_stress_conversion(self):
        self.assertAlmostEqual(convert_stress(4.0, "ksi", "psi"), 4000.0, places=2)
        self.assertAlmostEqual(convert_stress(4000.0, "psi", "ksi"), 4.0, places=2)
        self.assertAlmostEqual(convert_stress(1.0, "ksi", "mpa"), 6.89476, delta=1e-3)

    def test_moment_conversion(self):
        self.assertAlmostEqual(convert_moment(12.0, "kip-in", "kip-ft"), 1.0, places=2)
        self.assertAlmostEqual(convert_moment(1.0, "kip-ft", "kip-in"), 12.0, places=2)


if __name__ == "__main__":
    unittest.main()
