"""
Formatted design reports generation (Markdown, ASCII text, HTML).
"""

from .base import ReportBase
from .markdown_report import MarkdownReport
from .text_report import BeamTextReport

__all__ = [
    "ReportBase",
    "BeamTextReport",
    "MarkdownReport",
]
