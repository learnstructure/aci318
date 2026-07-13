from aci318.codes.base import DesignCode
from aci318.loads.load_effects import LoadEffects
from aci318.sections.rectangle import RectangleSection
from aci318.results.beam import BeamDesignResult
from aci318.strength.flexure.beam_engine import design_rectangular_beam_flexure
from aci318.strength.shear.beam_engine import design_rectangular_beam_shear

class Beam:
    """
    User-facing Beam class that coordinates calculations.
    It contains no structural design equations directly.
    """
    def __init__(self, section: RectangleSection, code: DesignCode) -> None:
        self.section = section
        self.code = code

    def design(self, loads: LoadEffects) -> BeamDesignResult:
        """
        Coordinates flexural and shear strength check for the beam.
        """
        # Run flexure engine
        flexure_res = design_rectangular_beam_flexure(self.section, self.code)
        
        # Run shear engine (using default stirrup properties for check)
        shear_res = design_rectangular_beam_shear(self.section, self.code)
        
        # Determine composite status
        status = "Passed"
        if flexure_res.status == "Failed" or shear_res.status == "Failed":
            status = "Failed"
        elif flexure_res.status == "Warning" or shear_res.status == "Warning":
            status = "Warning"
            
        # Combine messages
        messages = flexure_res.messages + shear_res.messages
        
        return BeamDesignResult(
            flexure=flexure_res,
            shear=shear_res,
            status=status,
            messages=messages
        )
