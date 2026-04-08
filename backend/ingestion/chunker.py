"""
ingestion/chunker.py

Splits a normalized markdown review into generic semantic chunks.
Each chunk becomes one record in the vector DB.

Strategy:
  - Detect ## or ### headings and group the text under it as a chunk.
  - If no headings are found, treat the full text as one chunk.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    heading: str                    # original heading text found in the doc
    content: str                    # raw markdown text of this section
    char_count: int = field(init=False)

    def __post_init__(self):
        self.char_count = len(self.content)

    def is_too_short(self, min_chars: int = 80) -> bool:
        """Flag sections that are suspiciously short (likely missing content)."""
        return self.char_count < min_chars


def split_by_headings(markdown: str) -> list[tuple[str, str]]:
    """
    Split markdown by ## or ### headings.
    Returns list of (heading_text, section_content) tuples.
    """
    pattern = re.compile(r"^#{2,3}\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(markdown))

    if not matches:
        return []

    segments = []
    # If there's text before the first heading, capture it too
    if matches[0].start() > 0:
        intro_content = markdown[:matches[0].start()].strip()
        if intro_content:
            segments.append(("Introduction", intro_content))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        content = markdown[start:end].strip()
        segments.append((heading, content))

    return segments


def chunk_review(markdown: str) -> list[Chunk]:
    """
    Main chunker entry point.

    Returns a list of generic Chunk objects.
    If no headings detected at all, returns a single full-doc chunk.
    """
    segments = split_by_headings(markdown)

    if not segments:
        return [Chunk(
            heading="[full document — no section headings detected]",
            content=markdown,
        )]

    chunks: list[Chunk] = []

    for heading, content in segments:
        if len(content.strip()) < 10:
            continue  # skip empty headings

        chunks.append(Chunk(
            heading=heading,
            content=content,
        ))

    return chunks
