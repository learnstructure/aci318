from abc import ABC, abstractmethod
from typing import Any


class DesignCode(ABC):
    """
    Abstract base class defining the design code interface for ACI 318.
    All code revisions (e.g., ACI 318-19, 318-25) must implement this interface.
    """

    @abstractmethod
    def get_phi_flexure(self, strain_t: float, spiral: bool = False) -> float:
        """Get strength reduction factor (phi) for flexure based on net tensile strain."""
        pass

    @abstractmethod
    def get_phi_shear(self) -> float:
        """Get strength reduction factor (phi) for shear."""
        pass

    @abstractmethod
    def get_phi_torsion(self) -> float:
        """Get strength reduction factor (phi) for torsion."""
        pass

    @abstractmethod
    def get_phi_axial(self, compression: bool, spiral: bool = False) -> float:
        """Get strength reduction factor (phi) for axial strength."""
        pass

    @abstractmethod
    def get_beta_1(self, f_c: float) -> float:
        """Get beta_1 factor for equivalent rectangular concrete stress block."""
        pass

    @abstractmethod
    def get_lambda_(self, concrete: Any) -> float:
        """Get lightweight concrete modification factor (lambda)."""
        pass

    @abstractmethod
    def get_minimum_steel_ratio(self, f_c: float = 4.0, f_y: float = 60.0) -> float:
        """Get minimum flexural reinforcement ratio."""
        pass

    @abstractmethod
    def get_vc(
        self,
        f_c: float,
        b_w: float,
        d: float,
        N_u: float = 0.0,
        A_g: float = 1.0,
        A_v: float = 0.0,
        A_v_min: float = 0.0,
        lambda_val: float = 1.0,
        rho_w: float = 0.01,
    ) -> float:
        """Get concrete shear strength Vc in kips."""
        pass

    @abstractmethod
    def get_threshold_torsion(
        self,
        f_c: float,
        Acp: float,
        pcp: float,
        N_u: float = 0.0,
        A_g: float = 1.0,
        lambda_val: float = 1.0,
    ) -> float:
        """Get threshold torsion Tth in kip-in."""
        pass

    @abstractmethod
    def get_cracking_torsion(
        self,
        f_c: float,
        Acp: float,
        pcp: float,
        N_u: float = 0.0,
        A_g: float = 1.0,
        lambda_val: float = 1.0,
    ) -> float:
        """Get cracking torsion Tcr in kip-in."""
        pass
