"""
test_local.py — smoke test for chunker and parser logic (no API keys needed)

Run with:
  python test_local.py
"""

import sys
import os

# So imports resolve from project root
sys.path.insert(0, os.path.dirname(__file__))

# ─── Test 1: Parser (plain text) ─────────────────────────────────────────────

from ingestion.parser import parse_plain_text

sample_review = """
# Review: Notion AI

## Pre-Test Research
Notion AI is a productivity tool integrated into Notion workspaces.
It provides AI-powered writing assistance, summarization, and task generation.
Target users are knowledge workers and teams using Notion for documentation.

## Test Design
Test cases designed to cover:
- Writing assistance: generate paragraph from a bullet list
- Summarization: summarize a 500-word document
- Action items: extract tasks from a meeting note
- Edge case: empty page input
- Edge case: non-English text input

## Hands-On Testing
TC-01 Writing assist | Input: 3 bullet points about project kickoff
  Expected: coherent paragraph | Actual: clean output, minor grammar issue → PASS

TC-02 Summarization | Input: 487-word product spec
  Expected: <100 word summary | Actual: 92 words, accurate → PASS

TC-03 Action items | Input: meeting transcript
  Expected: bulleted task list | Actual: tasks extracted but one missed → NOTE

TC-04 Empty page | Input: blank page
  Expected: graceful error | Actual: spinner indefinitely → FAIL

TC-05 Non-English | Input: Hindi paragraph
  Expected: assist in same language | Actual: responds in English → NOTE

## Gap Analysis
- No API access tested (Notion AI is UI-only — not a gap but a limitation)
- Mobile app behavior not tested
- Collaborative real-time editing with AI not covered

## Polished Report
Notion AI performs well on core use cases with strong summarization.
Key failure: empty page handling causes UI freeze.
Notable gap: non-English support is inconsistent.
Overall recommendation: suitable for English-speaking knowledge teams.
PASS with NOTEs on edge case handling.
"""

md = parse_plain_text(sample_review)
print("✓ Parser: plain text → markdown")
print(f"  Output length: {len(md)} chars\n")


# ─── Test 2: Chunker ──────────────────────────────────────────────────────────

from ingestion.chunker import chunk_review, get_missing_sections

chunks = chunk_review(md)
print(f"✓ Chunker: found {len(chunks)} sections")
for c in chunks:
    status = "⚠ SHORT" if c.is_too_short() else "ok"
    print(f"  → {c.section_type.value:<25} | {c.char_count} chars | {status}")

missing = get_missing_sections(chunks)
if missing:
    print(f"\n  Missing sections: {[s.value for s in missing]}")
else:
    print("  No missing sections ✓")


# ─── Test 3: Section detection with bad headings ──────────────────────────────

bad_review = """
## Introduction
This review covers a new tool.

## Our Testing Approach
We designed test cases.

## What We Found
Mixed results.

## Final Thoughts
Recommended with caveats.
"""

chunks2 = chunk_review(parse_plain_text(bad_review))
print(f"\n✓ Chunker (non-standard headings): found {len(chunks2)} sections")
for c in chunks2:
    print(f"  → '{c.heading}' → {c.section_type.value}")
missing2 = get_missing_sections(chunks2)
print(f"  Missing: {[s.value for s in missing2]}")


# ─── Test 4: Models validation ────────────────────────────────────────────────

from models import DimensionScore, Label, SectionScore, SectionType

score = DimensionScore(score=8, label=Label.PASS, rationale="Good coverage", suggestion=None)
section = SectionScore(
    section=SectionType.test_design,
    present_in_draft=True,
    retrieval_mode="rag_grounded",
    relevance=score,
    depth=score,
    precision=score,
    outcomes=score,
    coverage=score,
    overall_section_score=8.0,
)
print(f"\n✓ Models: SectionScore validates correctly")
print(f"  section={section.section.value}, overall={section.overall_section_score}")

print("\n\n✅ All smoke tests passed. Ready to connect API keys and run the server.")
