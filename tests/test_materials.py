import pytest
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel

def test_concrete_creation():
    concrete = Concrete(fc=4.0)
    assert concrete.fc == 4.0
    assert concrete.density == 145.0
    assert concrete.concrete_type == "normalweight"
    assert concrete.max_strain == 0.003
    # Check default Ec calculation for normal weight concrete
    # Ec = 57000 * sqrt(fc * 1000) / 1000 = 57 * sqrt(4000) = 57 * 63.2455 = 3604.996 ksi
    assert concrete.Ec == pytest.approx(3604.996, abs=1e-2)


def test_steel_creation():
    steel = Steel(fy=60.0)
    assert steel.fy == 60.0
    assert steel.Es == 29000.0
    assert steel.yield_strain == pytest.approx(60.0 / 29000.0)
