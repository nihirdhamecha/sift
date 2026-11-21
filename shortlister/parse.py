"""PDF -> plain text."""
from pathlib import Path

import pdfplumber


def pdf_to_text(path: Path) -> str:
    """Extract text from a PDF. Returns '' for scanned/image-only PDFs."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()
