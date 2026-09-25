# BJ-2023-FT-YIMO exact change audit

## Candidate byte identity

All 22 candidate question files are copied byte-for-byte: **22/22 SHA unchanged**. All four candidate image files are also byte-for-byte unchanged. The old controller-ready candidate manifest SHA is `f5ed17824b4a0b7e224cf79a7a5db60aa09283d33bee63bf072dadfadabb0d47`.

No question text, embedded answer, analysis, explanation, Q17 wording, Q20 carry-over sentence, or candidate image was edited. The new candidate manifest is a navigation/identity manifest for this self-contained package; the old manifest is retained under `history/`.

## Old versus active source support

| Item | Old controller-ready support | Active canonical support |
|---|---|---|
| Flat transcript | 301 lines / 43,499 bytes; omitted all six table bodies | Markdown + compatible TXT generated from all 308 sequenced native records; 302 paragraphs + 6 tables + 4 media positions |
| Table coverage | Table bodies only reachable through question candidates | All 6 native `struct` records embedded in active transcript and `sources/native/table_structs.json` |
| Media | Candidate image copies existed | Four byte-identical copies and parseable transcript links at seq 1, 100, 199, 255 |
| Visual page support | Historical 14-page missing-glyph derivative | Existing 35-page readable PDF/PNG witness and active 35-page `page_coverage.json` |
| Footer | Not carried in flat transcript | Raw `footer1.xml`/`footer2.xml` plus SHA registry; dynamic PAGE/SECTIONPAGES, cached 1/3 only |
| Old material | Active-path incomplete transcript and 14-page map | Moved to `history/raw_history/` and history metadata; not active locators |

## Evidence limits retained

This is source completion, not authority/full acceptance. The only source is a teacher-version/transcription DOCX (E3/source material only). No independent original, independent answer, formal E1 rubric, reliable scores, student responses or annotations were provided. `points_total=null`. `shared_modified=[]`.
