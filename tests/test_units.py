import pytest
from aci318.utils.units import (
    convert_force, 
    convert_length, 
    convert_stress, 
    convert_moment,
    IN_TO_MM,
    MM_TO_IN
)

def test_length_conversion():
    assert convert_length(1.0, "in", "mm") == pytest.approx(25.4)
    assert convert_length(25.4, "mm", "in") == pytest.approx(1.0)
    assert convert_length(1.0, "ft", "in") == pytest.approx(12.0)
    assert convert_length(12.0, "in", "ft") == pytest.approx(1.0)


def test_force_conversion():
    assert convert_force(1.0, "kip", "lb") == pytest.approx(1000.0)
    assert convert_force(1000.0, "lb", "kip") == pytest.approx(1.0)
    assert convert_force(1.0, "kip", "kn") == pytest.approx(4.44822, abs=1e-3)


def test_stress_conversion():
    assert convert_stress(4.0, "ksi", "psi") == pytest.approx(4000.0)
    assert convert_stress(4000.0, "psi", "ksi") == pytest.approx(4.0)
    assert convert_stress(1.0, "ksi", "mpa") == pytest.approx(6.89476, abs=1e-3)


def test_moment_conversion():
    assert convert_moment(12.0, "kip-in", "kip-ft") == pytest.approx(1.0)
    assert convert_moment(1.0, "kip-ft", "kip-in") == pytest.approx(12.0)
