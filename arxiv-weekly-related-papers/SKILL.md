---
name: arxiv-weekly-related-papers
description: Find arXiv papers related to given seed arXiv IDs by querying the arXiv API, filtering recent papers from the previous week or a requested date range, limiting categories such as hep-ex, nucl-ex, hep-ph, and nucl-th, ranking candidates by explainable text/category/author overlap, and writing a Markdown literature report. Use when asked to monitor recent high-energy or nuclear physics literature, collect related papers for one or more arXiv IDs, or generate weekly arXiv related-paper summaries.
---

# arXiv Weekly Related Papers

## Workflow

1. Normalize the seed arXiv IDs.
   - Accept forms like `2301.01234`, `arXiv:2301.01234`, `hep-ph/9701234`, and versioned IDs like `2301.01234v2`.
   - Preserve versions only when fetching exact seed metadata; compare related papers by unversioned ID.

2. Run the bundled script from the skill directory:

   ```bash
   python3 scripts/fetch_related_arxiv.py --ids 2301.01234,2405.06789 --output related.md
   ```

3. Use the default date behavior unless the user specifies otherwise.
   - Default range is the last 7 UTC days ending at the run time.
   - Use `--start-date YYYY-MM-DD --end-date YYYY-MM-DD` for an explicit closed date range.

4. Keep the default categories unless the user requests a different physics scope.
   - Defaults: `hep-ex`, `nucl-ex`, `hep-ph`, `nucl-th`.
   - Override with comma-separated values: `--categories hep-ex,hep-ph`.

5. Review the generated Markdown before responding.
   - The script ranks relatedness heuristically; arXiv does not provide a native "related papers" endpoint.
   - Do not claim the list is exhaustive. State that it is an API-based candidate set ranked by title, abstract, category, and author overlap.
   - If the user asked for Chinese output, keep the Markdown headings and notes in Chinese; titles and abstracts should remain faithful to the arXiv metadata unless translating is explicitly requested.

## Script Options

Use `scripts/fetch_related_arxiv.py` for the API work and report generation.

Important options:

- `--ids`: Required seed arXiv IDs, comma-separated or space-separated.
- `--output`: Markdown output path. Defaults to `arxiv_related_<date>.md`.
- `--days`: Lookback window in UTC days. Defaults to `7`.
- `--start-date`, `--end-date`: Explicit UTC date range, inclusive.
- `--categories`: Comma-separated arXiv categories. Defaults to `hep-ex,nucl-ex,hep-ph,nucl-th`.
- `--max-candidates`: Maximum recent category papers fetched before scoring. Defaults to `1000`.
- `--top-n`: Number of ranked related papers to include. Defaults to `50`.
- `--min-score`: Minimum relatedness score. Defaults to `2.5`.
- `--language`: `zh` or `en` for report labels. Defaults to `zh`.

If network access is blocked by the execution environment, request approval to rerun the script with network access rather than fabricating results.

## Output Expectations

The Markdown report should include:

- Query parameters and date range.
- Seed paper metadata.
- Ranked related papers with arXiv ID, title, categories, authors, dates, score, matched keywords, and links.
- A "no results" note when no candidate clears the threshold.
- A short methodology note explaining the heuristic ranking.
