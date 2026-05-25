import re
from typing import Any
import logging
from docxtpl import RichText

logger = logging.getLogger(__name__)

class RichTextRenderer:
    """
    Recursively converts flat resume data fields containing special formatting tokens 
    (e.g., [:B:], [:L1:]) into docxtpl.RichText objects for final rendering.
    """

    def apply_rendering_actions(self, data: Any, current_key: str = None) -> Any:
        """
        Recursively pass through the data to convert CVML tags into docxtpl objects.
        """
        if isinstance(data, dict):
            # Process each value in the dictionary
            return {
                k: self.apply_rendering_actions(v, current_key=k)
                for k, v in data.items()
                if k != "_"
            }

        elif isinstance(data, list):
            # Process each item in the list
            return [self.apply_rendering_actions(item, current_key=current_key) for item in data]

        elif isinstance(data, str):
            # Check for CVML tags, line breaks, or if it's a _str field that must be RichText
            force_rich_text = bool(current_key and current_key.endswith("_str"))
            if force_rich_text or "[:" in data or "\n" in data:
                return self._parse_rich_text(data)
            return data

        return data

    def _parse_rich_text(self, text: str) -> Any:
        """Converts CVML tags like [:B:], [:L1:], etc. into docxtpl RichText."""
        if not text:
            return ""

        rt = RichText()
        text = text.replace("\r\n", "\n")

        # Tokenize by tags
        parts = re.split(r"(\[:/?(?:B|I|U|L|C|H\d|PIPE|BR|L1|L2):?\])", text)

        active_bold = False
        active_italic = False

        for part in parts:
            if not part:
                continue

            if part == "[:B:]":
                active_bold = True
            elif part == "[:/B:]":
                active_bold = False
            elif part == "[:I:]":
                active_italic = True
            elif part == "[:/I:]":
                active_italic = False
            elif part == "[:PIPE:]":
                rt.add("  |  ")
            elif part == "[:BR:]":
                rt.add("\n")
            elif part == "[:L1:]":
                rt.add("\n• ")
            elif part == "[:L2:]":
                rt.add("\n    - ")
            elif part.startswith("[:"):
                continue  # Ignore unknown tags
            else:
                # Actual content
                rt.add(part, bold=active_bold, italic=active_italic)

        return rt
