"""
Base Utility Bill Module
"""

from abc import ABC, abstractmethod
import os
from typing import Dict, Any
import pdfplumber


class UtilityBill(ABC):
    """Abstract Base Class representing a general utility bill."""

    provider: str = ""
    utility: str = ""

    def __init__(self, filepath: str):
        self.filepath = str(filepath)
        self.filename = os.path.basename(self.filepath)
        self.full_text = ""
        self.text_ns = ""
        self._extract_text()

    def _extract_text(self):
        """Extract text from the PDF file using pdfplumber."""
        with pdfplumber.open(self.filepath) as pdf:
            self.full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.text_ns = self.full_text.replace(" ", "")

    @abstractmethod
    def parse(self) -> Dict[str, Any]:
        """Extract bill attributes and return a dictionary of fields."""
        pass
