"""ExtractionAgent – extracts raw text from PDF, DOCX, and image files."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Union


class ExtractionAgent:
    """Extract raw text from various document formats.

    Supported formats
    -----------------
    * ``.pdf``  – uses *pypdf*
    * ``.docx`` – uses *python-docx*
    * ``.png``, ``.jpg``, ``.jpeg``, ``.tiff``, ``.bmp``, ``.gif``
                – uses *Pillow* + *pytesseract* (OCR)

    The agent accepts a file path (``str`` or ``pathlib.Path``) **or** raw
    ``bytes`` together with an explicit ``extension`` hint.
    """

    _IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}
    _PDF_EXTENSION = ".pdf"
    _DOCX_EXTENSION = ".docx"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        source: Union[str, Path, bytes],
        extension: str = "",
    ) -> str:
        """Return extracted plain text from *source*.

        Parameters
        ----------
        source:
            A file-system path, or raw bytes when ``extension`` is given.
        extension:
            File extension (including the leading dot, e.g. ``".pdf"``).
            Required when *source* is ``bytes``; ignored otherwise.

        Returns
        -------
        str
            Extracted text, or an empty string if nothing could be read.
        """
        if isinstance(source, (str, Path)):
            path = Path(source)
            extension = path.suffix.lower()
            data = path.read_bytes()
        else:
            data = source
            extension = extension.lower()

        if extension == self._PDF_EXTENSION:
            return self._extract_pdf(data)
        if extension == self._DOCX_EXTENSION:
            return self._extract_docx(data)
        if extension in self._IMAGE_EXTENSIONS:
            return self._extract_image(data)

        raise ValueError(
            f"Unsupported file extension {extension!r}. "
            f"Expected one of: .pdf, .docx, .png, .jpg, .jpeg, .tiff, .bmp, .gif"
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pdf(data: bytes) -> str:
        """Extract text from a PDF byte stream using *pypdf*."""
        try:
            import pypdf  # type: ignore[import]
        except ModuleNotFoundError as exc:
            raise ImportError(
                "pypdf is required for PDF extraction. Install it with: pip install pypdf"
            ) from exc

        reader = pypdf.PdfReader(io.BytesIO(data))
        pages: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages.append(text)
        return "\n".join(pages)

    @staticmethod
    def _extract_docx(data: bytes) -> str:
        """Extract text from a DOCX byte stream using *python-docx*."""
        try:
            import docx  # type: ignore[import]
        except ModuleNotFoundError as exc:
            raise ImportError(
                "python-docx is required for DOCX extraction. "
                "Install it with: pip install python-docx"
            ) from exc

        document = docx.Document(io.BytesIO(data))
        paragraphs: list[str] = [para.text for para in document.paragraphs if para.text]
        return "\n".join(paragraphs)

    @staticmethod
    def _extract_image(data: bytes) -> str:
        """Extract text from an image byte stream using Pillow + pytesseract (OCR)."""
        try:
            from PIL import Image  # type: ignore[import]
        except ModuleNotFoundError as exc:
            raise ImportError(
                "Pillow is required for image extraction. Install it with: pip install Pillow"
            ) from exc
        try:
            import pytesseract  # type: ignore[import]
        except ModuleNotFoundError as exc:
            raise ImportError(
                "pytesseract is required for image extraction. "
                "Install it with: pip install pytesseract"
            ) from exc

        image = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(image)
