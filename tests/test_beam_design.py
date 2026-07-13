import pytest
from aci318.codes.aci318_19 import ACI318_19
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.loads.load_effects import LoadEffects
from aci318.members.beam import Beam

def test_beam_flexural_and_shear_design():
    # 1. Setup materials
    concrete = Concrete(fc=4.0)  # 4 ksi concrete
    steel = Steel(fy=60.0)      # Grade 60 steel
    
    # 2. Setup rectangular section (12x24 inches)
    section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
    
    # Add rebar: 3 #8 bars at 21.5 in depth (3 * 0.79 = 2.37 in^2 area)
    section.add_rebar_layer(area=2.37, depth=21.5, steel=steel)
    
    # 3. Setup ACI 318-19 code
    code = ACI318_19()
    
    # 4. Instantiate Beam coordinator
    beam = Beam(section=section, code=code)
    
    # 5. Define load effects
    loads = LoadEffects(Pu=0.0, Mu=2500.0, Vu=30.0, Tu=0.0)
    
    # 6. Run design
    result = beam.design(loads)
    
    # 7. Asserts
    assert result.status in ("Passed", "Warning") # Should pass or raise minor warnings (e.g. min steel ratio checks)
    assert result.flexure.provided_steel == 2.37
    assert result.flexure.phi_mn > 0.0
    assert result.shear.vn_concrete > 0.0
    assert result.shear.phi_vn > 0.0
    
    # Verify calculated neutral axis and moment capacity
    # a = As * fy / (0.85 * fc * b) = 2.37 * 60 / (0.85 * 4 * 12) = 142.2 / 40.8 = 3.485 in
    # c = a / beta_1 = 3.485 / 0.85 = 4.10 in
    # strain_t = 0.003 * (21.5 - 4.10) / 4.10 = 0.0127 (tension-controlled since > 0.005)
    # phi = 0.90
    # Mn = T * (d - a/2) = (2.37 * 60) * (21.5 - 3.485/2) = 142.2 * 19.757 = 2809.5 kip-in
    # phi*Mn = 0.90 * 2809.5 = 2528.5 kip-in
    assert result.flexure.neutral_axis == pytest.approx(4.10, abs=0.1)
    assert result.flexure.steel_strain == pytest.approx(0.0127, abs=0.001)
    assert result.flexure.phi_mn == pytest.approx(2528.5, abs=5.0)
