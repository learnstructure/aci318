"""
Abstract base class for all report generators.
Reporters format result objects into human-readable output.

Rules:
  - Reporters never perform calculations.
  - Reporters only consume result objects, section, loads, and metadata.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class ReportBase(ABC):
    """Abstract base class for all design report generators."""

    @abstractmethod
    def generate(self) -> str:
        """
        Generate the formatted report as a string.

        Returns:
            str: The full report content.
        """
        pass

    def print_to_console(self) -> None:
        """Print the generated report to stdout."""
        print(self.generate())

    def save(self, filepath: str) -> None:
        """
        Save the generated report to a file.

        Args:
            filepath: Absolute or relative path where the report should be saved.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.generate(), encoding="utf-8")
        print(f"Report saved → {path.resolve()}")
