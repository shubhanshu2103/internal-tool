"""
ingestion/parser.py

Converts uploaded PDF or DOCX files to clean markdown text.
Uses pymupdf4llm for PDFs (preserves heading hierarchy better than raw PyMuPDF)
and python-docx for Word files.

Output is always normalized markdown — same format regardless of source.
"""

import re
import tempfile
from pathlib import Path


def parse_pdf(file_bytes: bytes) -> str:
    """Extract markdown text from a PDF file."""
    import pymupdf4llm

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        md_text = pymupdf4llm.to_markdown(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return _clean_markdown(md_text)


def parse_docx(file_bytes: bytes) -> str:
    """Extract markdown text from a DOCX file."""
    import docx
    import io

    doc = docx.Document(io.BytesIO(file_bytes))
    lines = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue

        style = para.style.name.lower() if para.style and para.style.name else ""

        if "heading 1" in style:
            lines.append(f"# {text}")
        elif "heading 2" in style:
            lines.append(f"## {text}")
        elif "heading 3" in style:
            lines.append(f"### {text}")
        else:
            lines.append(text)

    return _clean_markdown("\n".join(lines))


def parse_plain_text(text: str) -> str:
    """Accept raw pasted text — minimal cleanup only."""
    return _clean_markdown(text)


def parse_file(file_bytes: bytes, filename: str) -> str:
    """
    Auto-detect file type from extension and parse accordingly.
    Returns normalized markdown string.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return parse_pdf(file_bytes)
    elif ext in (".docx", ".doc"):
        return parse_docx(file_bytes)
    elif ext in (".txt", ".md"):
        return parse_plain_text(file_bytes.decode("utf-8", errors="replace"))
    else:
        raise ValueError(f"Unsupported file type: {ext}. Accepted: .pdf .docx .txt .md")


def _clean_markdown(text: str) -> str:
    """
    Normalize markdown:
    - Collapse 3+ blank lines into 2
    - Strip trailing whitespace per line
    - Ensure headings have a space after #
    """
    # Ensure space after #
    text = re.sub(r"^(#{1,4})([^#\s])", r"\1 \2", text, flags=re.MULTILINE)
    # Strip trailing whitespace
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
