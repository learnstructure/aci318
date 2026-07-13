from aci318.codes.base import DesignCode
from aci318.loads.load_effects import LoadEffects
from aci318.sections.rectangle import RectangleSection
from aci318.results.column import ColumnDesignResult
from aci318.strength.axial.column_engine import calculate_axial_capacity
from aci318.strength.shear.beam_engine import design_rectangular_beam_shear  # generic shear

class Column:
    """
    User-facing Column class that coordinates calculations.
    It contains no structural design equations directly.
    """
    def __init__(self, section: RectangleSection, code: DesignCode) -> None:
        self.section = section
        self.code = code

    def design(self, loads: LoadEffects) -> ColumnDesignResult:
        """
        Coordinates axial/flexural and shear checks for the column.
        """
        # Run axial strength calculation (simplified for flexure/axial representation)
        axial_res = calculate_axial_capacity(self.section, self.code)
        
        # In a complete implementation, this would verify PM interaction curves.
        # For this skeleton, we map to FlexureResult-compatible structure
        from aci318.results.flexure import FlexureResult
        flexure_mapped = FlexureResult(
            required_steel=0.0,
            provided_steel=sum(l.area for l in self.section.layers),
            neutral_axis=0.0,
            steel_strain=0.005,
            phi_mn=axial_res.phi_pn_max,  # map capacity
            status=axial_res.status,
            messages=axial_res.messages
        )
        
        shear_res = design_rectangular_beam_shear(self.section, self.code)
        
        # Composite status
        status = "Passed"
        if axial_res.status == "Failed" or shear_res.status == "Failed":
            status = "Failed"
        elif axial_res.status == "Warning" or shear_res.status == "Warning":
            status = "Warning"
            
        return ColumnDesignResult(
            axial_flexure=flexure_mapped,
            shear=shear_res,
            status=status,
            messages=axial_res.messages + shear_res.messages
        )
