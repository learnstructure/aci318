from abc import ABC, abstractmethod
from typing import Any

# We use typing.Any for Concrete/Steel materials in the base code 
# to avoid circular imports, or we can type hint them cleanly.

class DesignCode(ABC):
    """
    Abstract base class defining the design code interface for ACI 318.
    All code revisions (e.g., ACI 318-19, 318-25) must implement this interface.
    """

    @abstractmethod
    def get_phi_flexure(self, strain_t: float) -> float:
        """
        Get the strength reduction factor (phi) for flexure based on the net tensile strain.
        
        Args:
            strain_t: Net tensile strain in extreme tension steel.
            
        Returns:
            float: Strength reduction factor.
        """
        pass

    @abstractmethod
    def get_phi_shear(self) -> float:
        """
        Get the strength reduction factor (phi) for shear.
        
        Returns:
            float: Strength reduction factor.
        """
        pass

    @abstractmethod
    def get_phi_axial(self, compression: bool) -> float:
        """
        Get the strength reduction factor (phi) for axial strength.
        
        Args:
            compression: True if member is compression-controlled, False if tension-controlled.
            
        Returns:
            float: Strength reduction factor.
        """
        pass

    @abstractmethod
    def get_beta_1(self, f_c: float) -> float:
        """
        Get the beta_1 factor for the equivalent rectangular concrete stress block.
        
        Args:
            f_c: Concrete compressive strength (ksi).
            
        Returns:
            float: beta_1 factor.
        """
        pass

    @abstractmethod
    def get_lambda_(self, concrete: Any) -> float:
        """
        Get the lightweight concrete modification factor (lambda).
        
        Args:
            concrete: Concrete material object.
            
        Returns:
            float: lambda modification factor.
        """
        pass

    @abstractmethod
    def get_minimum_steel_ratio(self) -> float:
        """
        Get the minimum flexural reinforcement ratio.
        
        Returns:
            float: Minimum steel ratio.
        """
        pass
