from aci318.codes.aci318_19 import ACI318_19
from aci318.loads.load_effects import LoadEffects
from aci318.materials.concrete import Concrete
from aci318.materials.steel import Steel
from aci318.sections.rectangle import RectangleSection
from aci318.strength import AxialStrength, FlexureStrength, InteractionStrength, ShearStrength


def test_strength_objects_provide_demand_capacity_ratios():
    concrete = Concrete(fc=4.0)
    steel = Steel(fy=60.0)
    code = ACI318_19()

    section = RectangleSection(b=12.0, h=24.0, concrete=concrete)
    section.add_rebar_layer(area=2.37, depth=21.5, steel=steel)

    flexure = FlexureStrength(section=section, code=code)
    result = flexure.check(loads=LoadEffects(Mu=2500.0))
    assert result.status in {"Passed", "Warning"}
    assert result.demand_capacity_ratio > 0.0

    shear = ShearStrength(section=section, code=code)
    shear_result = shear.check(loads=LoadEffects(Vu=30.0))
    assert shear_result.status in {"Passed", "Warning"}
    assert shear_result.demand_capacity_ratio > 0.0

    axial = AxialStrength(section=section, code=code)
    axial_result = axial.check(loads=LoadEffects(Pu=100.0))
    assert axial_result.status in {"Passed", "Warning"}
    assert axial_result.demand_capacity_ratio > 0.0

    interaction = InteractionStrength(section=section, code=code)
    interaction_result = interaction.check(loads=LoadEffects(Pu=100.0, Mu=2500.0))
    assert interaction_result.status in {"Passed", "Warning"}
    assert interaction_result.demand_capacity_ratio > 0.0
