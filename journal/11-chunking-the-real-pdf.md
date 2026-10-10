# Chunking against the real PDF

**Date:** 2026-10-09

## Context
The first chunker was written against search-engine snippets of an older issue and
tested on synthetic text. Run on the real Issue 09 PDF, retrieval already worked, but the
chunks were wrong in ways the tests could not catch.

## Findings
- PyMuPDF puts the article number, its heading and the text on separate lines. The
  chunker expected "B1.2 Title" on one line, so every title came out empty.
- The table of contents slipped in as chunks ("B1.9 Incidents... 14 ARTICLE B2...").
- The page header changed between issues ("0 B" / "B47" / "Issue 09"), so it was glued
  into the middle of article text.
- Appendix B5 lists the approved 2027 changes reusing 2026 numbers (B2.5.2 with 305 km);
  "keep the longest version" could pick the 2027 text for a 2026 rule.
- Lines like "B5.15.2 shall remain unchanged..." are wrapped cross-references, not new
  articles: only a number alone on its line starts an article.
- The FIA itself numbers two different sub-articles B1.5.11 (Rain Hazard and Normal &
  Low Grip Conditions), so ids are made unique while the citation is kept.
- One chunk was 16k characters. all-MiniLM-L6-v2 reads ~256 word pieces, so everything
  after the first ~1,000 characters was invisible to search.

## Decision
- Skip the TOC (body starts at the second "ARTICLE B1:") and drop everything from
  Appendix B3 on. Keep Appendix B1 (one chunk per definition) and B2 (parc fermé works).
- Title = heading path ("Safety Car (SC) > During a SC Deployment"), detected as short
  Title Case lines right after a number. Embedded together with the text.
- Split chunks over 1,000 characters on sentence boundaries (`B5.13.2#1`, `#2`).
- Tests now use lines copied from the real PDF layout, including a page break in the
  middle of a sentence.

## Consequences
- 323 → 459 chunks, every one with a title, none over 1,000 characters.
- Lesson: test a parser on the real document early; synthetic data only checks the
  assumptions you already had.
