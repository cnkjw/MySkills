---
name: arxiv-weekly-related-papers
description: Find arXiv papers related to given seed arXiv IDs by querying the arXiv API, filtering recently updated or submitted papers from the previous week or a requested date range, limiting categories such as hep-ex, nucl-ex, hep-ph, and nucl-th, preparing an abstract analysis packet, then using the executing AI assistant (Codex, opencode, Claude Code, etc.) to judge relevance and recommendation strength and write a Markdown literature report with selected papers and research-extension ideas. Use when asked to monitor recent high-energy or nuclear physics literature, collect related papers for one or more arXiv IDs, or generate weekly AI-assisted arXiv related-paper summaries.
---

# arXiv Weekly Related Papers

## Workflow

1. Normalize the seed arXiv IDs.
   - Accept forms like `2301.01234`, `arXiv:2301.01234`, `hep-ph/9701234`, and versioned IDs like `2301.01234v2`.
   - Preserve versions only when fetching exact seed metadata; compare related papers by unversioned ID.

2. Run the bundled script from the skill directory to fetch arXiv metadata and create an analysis packet:

   ```bash
   python3 scripts/fetch_related_arxiv.py --ids 2301.01234,2405.06789 --packet-output arxiv_packet.md --json-output arxiv_packet.json
   ```

3. Use the default date behavior unless the user specifies otherwise.
   - Default range is the last 7 UTC days ending at the run time.
   - Default date field is `lastUpdatedDate`, so revisions as well as new submissions can be included. In this mode the script sorts arXiv results by `lastUpdatedDate` and filters the returned `<updated>` dates locally.
   - Use `--start-date YYYY-MM-DD --end-date YYYY-MM-DD` for an explicit closed date range.
   - Use `--date-field submittedDate` when the user only wants first submissions.

4. Keep the default categories unless the user requests a different physics scope.
   - Defaults: `hep-ex`, `nucl-ex`, `hep-ph`, `nucl-th`.
   - Override with comma-separated values: `--categories hep-ex,hep-ph`.

5. Analyze the packet with the current AI assistant.
   - Read `arxiv_packet.md` or `arxiv_packet.json`.
   - Evaluate every candidate paper against the seed-paper abstracts. If the packet is too large for one pass, process it batch by batch and keep a compact intermediate table of evaluations.
   - Do not use local keyword/category/author-overlap scoring. Use the executing assistant's model judgment from the titles, abstracts, categories, and metadata in the packet.
   - For each candidate, assign `relevance_score` and `recommendation_score` from 0 to 100, choose `relation_type` from `direct`, `method`, `background`, `contrast`, `weak`, `not_related`, and write concise reasons.
   - For selected papers, provide concrete extension ideas or ways to combine the paper with the seed-paper research.

6. Write the final Markdown report requested by the user.
   - Do not claim the list is exhaustive. State that it is an arXiv API candidate set analyzed by the executing AI assistant from metadata and abstracts.
   - If the user asked for Chinese output, keep the Markdown headings and notes in Chinese; titles and abstracts should remain faithful to the arXiv metadata unless translating is explicitly requested.

## Script Options

Use `scripts/fetch_related_arxiv.py` for arXiv API fetching and packet generation. The script does not call an LLM API and does not require an AI provider API key.

Important options:

- `--ids`: Required seed arXiv IDs, comma-separated or space-separated.
- `--packet-output`: Markdown packet path for the executing AI assistant to read. Defaults to `arxiv_candidate_packet_<date>.md`.
- `--json-output`: Optional JSON packet path with the same papers and metadata.
- `--days`: Lookback window in UTC days. Defaults to `7`.
- `--start-date`, `--end-date`: Explicit UTC date range, inclusive.
- `--categories`: Comma-separated arXiv categories. Defaults to `hep-ex,nucl-ex,hep-ph,nucl-th`.
- `--date-field`: `lastUpdatedDate` or `submittedDate`. Defaults to `lastUpdatedDate`.
- `--max-candidates`: Maximum recent category papers fetched into the packet. Defaults to `1000`.
- `--batch-size`: Number of candidate papers per Markdown batch. Defaults to `20`.
- `--language`: `zh` or `en` for packet instructions. Defaults to `zh`.

If network access is blocked by the execution environment, request approval to rerun the script with network access rather than fabricating results. The script only requires access to `export.arxiv.org`.

## Output Expectations

The Markdown report should include:

- Query parameters and date range.
- Seed paper metadata.
- AI-selected papers with arXiv ID, title, categories, authors, dates, relevance score, recommendation score, relation type, reasoning, links, and research-extension ideas.
- A complete list or compact appendix of all evaluated candidate papers.
- A "no results" note when no candidate is worth recommending.
- A short methodology note explaining that the arXiv script only fetched metadata and the executing AI assistant evaluated the abstracts.
