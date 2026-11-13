# Manual test audit

The author confirmed the 15 grounding labels on 2026-11-14 after reviewing them against the saved top-3 traces; AI assistance was used to recheck evidence coverage.

Grounding scale: 0 = no answer evidence; 1 = partial evidence or missing a required condition; 2 = sufficient evidence to answer and trace to source.

| Strategy | Scores q16–q20 | Distribution (0 / 1 / 2) | Mean / 2 |
|---|---|---:|---:|
| A_fixed | 0, 2, 0, 2, 0 | 3 / 0 / 2 | 0.8 |
| B_paragraph | 1, 0, 0, 2, 0 | 3 / 1 / 1 | 0.6 |
| C_paragraph_metadata | 1, 0, 0, 2, 2 | 2 / 1 / 2 | 1.0 |

## Metadata review

- `document_id`, `source`, and `page` are present and match the manifest/PDF trace on all 15 retrieved records per strategy.
- `section` is present on 9/15 A records, 13/15 B records, and 14/15 C records. Pages outside the defined section ranges account for the observed gaps; record this as a metadata limitation.
- Where present or absent, `section` agrees with the page metadata map on all 15 records per strategy. Chunk text maps to the recorded physical PDF page on all 45 test hits.
- For C's four filtered test questions (q17–q20), all 12/12 top-3 records match `section=Thời kỳ hiện đại`.
- q16 is unfiltered; its C top-3 includes one page-26 hit without `section`.

## Notes

- q16 receives 1 for B/C because the retrieved passage supports the 1975 end of the war but omits the 1976 reunification year. A's top-3 does not give the requested years.
- q17 receives 2 for A because rank 1 contains the declaration evidence; B/C do not retrieve it in the top-3.
- q19 receives 2 for all strategies because rank 1 contains the peak date and troop count.
- q20 receives 2 for C because rank 3 contains the December 1986 evidence; A/B do not retrieve it in the top-3.

