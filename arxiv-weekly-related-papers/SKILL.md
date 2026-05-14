---
name: arxiv-weekly-related-papers
description: Find arXiv papers related to given seed arXiv IDs by querying the arXiv API, filtering recently updated or submitted papers from the previous week or a requested date range, using command-line or JSON config focus categories such as hep-ex, nucl-ex, hep-ph, and nucl-th, excluding unwanted cross-list categories before AI analysis to save context, preparing an abstract analysis packet, then using the executing AI assistant (Codex, opencode, Claude Code, etc.) to judge relevance and recommendation strength and write a Markdown literature report with selected papers and research-extension ideas. Use when asked to monitor recent high-energy or nuclear physics literature, collect related papers for one or more arXiv IDs, or generate weekly AI-assisted arXiv related-paper summaries.
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
   - Or use a JSON config file. When `--config` is omitted, the script automatically checks:

     - `~/.arxiv-weekly-related-papers/config.json`
     - `~/.arxiv-weekly-related-papers/arxiv_weekly_config.json`

     Example config:

     ```json
     {
       "categories": ["hep-ex", "nucl-ex", "hep-ph", "nucl-th"],
       "exclude_categories": ["astro-ph.CO", "gr-qc"]
     }
     ```

     Run with `--config arxiv_weekly_config.json` to use a project-specific config. Command-line `--categories` and `--exclude-categories` override config values.
5. Exclude unwanted cross-list categories before AI analysis when token budget matters.

   - Use `--exclude-categories astro-ph.CO,gr-qc`.
   - If any candidate paper has a category matching the exclude list, omit that paper from the Markdown/JSON packet entirely.
   - The packet records only exclusion counts by category, not excluded abstracts.
6. Analyze the packet with the current AI assistant.

   - Read `arxiv_packet.md` or `arxiv_packet.json`.
   - Evaluate every candidate paper against the seed-paper abstracts. If the packet is too large for one pass, process it batch by batch and keep a compact intermediate table of evaluations.
   - Do not use local keyword/category/author-overlap scoring. Use the executing assistant's model judgment from the titles, abstracts, categories, and metadata in the packet.
   - For each candidate, assign `relevance_score` and `recommendation_score` from 0 to 100, choose `relation_type` from `direct`, `method`, `background`, `contrast`, `weak`, `not_related`, and write concise reasons.
   - For selected papers, provide concrete extension ideas or ways to combine the paper with the seed-paper research.
7. Write the final Markdown report requested by the user.

   - Use the fixed report structure below unless the user explicitly asks for another format.
   - Do not claim the list is exhaustive. State that it is an arXiv API candidate set analyzed by the executing AI assistant from metadata and abstracts.
   - If the user asked for Chinese output, keep the Markdown headings and notes in Chinese; titles and abstracts should remain faithful to the arXiv metadata unless translating is explicitly requested.

## Final Report Format

Use this Markdown structure for the final report:

1. `# arXiv 周报：<种子数量或核心主题>相关候选分析`
2. `## 查询参数`
   - Use exactly this field order and label style. Fill values dynamically from `arxiv_packet.md` or `arxiv_packet.json`; do not copy placeholder values.
     - `- **生成时间**：<generated time>`
     - `- **日期范围**：<start date> 至 <end date>（UTC，含端点）`
     - `- **日期字段**：<date_field>`
     - `- **关注类别**：<focus_categories joined by ", ">`
     - `- **排除类别**：<exclude_categories joined by ", " or "无">`
     - `- **候选论文总数**：<candidate paper count>`
     - `- **AI 分析前排除**：<excluded_candidate_count>`
   - Keep labels in Chinese, bold them, and use the full-width colon `：`.
3. `## 种子论文概览`
   - First summarize the shared research theme in one short paragraph.
   - For multiple seed papers, group them into 2-4 subdirections such as "喷注修整与轴角度", "光子标记喷注与实验观测", or "多喷注拓扑与事件形状".
   - Use compact tables with columns like `arXiv ID`, `核心内容`, and `方法`.
   - Add one short line for shared methodological features when useful.
4. `## AI 精选论文`
   - Group selected papers by relation type in this order: `direct`, `method`, `background`, `weak`.
   - Use Chinese group headings such as `### 一、直接相关（direct）——喷注展宽与能量损失`.
   - For each selected paper, use a numbered `####` heading containing arXiv link and title.
   - Use exactly this metadata bullet format under each selected paper heading:
     - `- **作者**：<authors joined by ", ">`
     - `- **类别**：<categories joined by ", ">`
     - `- **发表/更新**：<published date>` when published and updated dates are the same, otherwise `- **发表/更新**：<published date> / <updated date>`
     - `- **相关度评分**：<relevance_score>/100`
     - `- **推荐度评分**：<recommendation_score>/100`
     - `- **关系类型**：<relation_type>`
   - Do not use English labels like `Authors`, `Categories`, `Published/Updated`, `Relevance score`, or inline semicolon-separated metadata.
   - Before `相关理由`, include two abstract paragraphs in this exact order:
     - `**Abstract:** <original summary from arxiv_packet.md/json>`
     - `**摘要：** <AI Chinese translation of the Abstract>`
   - Then include three bold paragraphs: `相关理由`, `推荐理由`, and `拓展研究思路`.
   - Use bullets for research ideas. Keep them concrete and actionable.
   - Preserve LaTeX math delimiters from arXiv text. Keep inline math as `$...$` and display math as `$$...$$`; never wrap LaTeX formulas in backticks because that prevents Markdown math rendering.
5. `## 候选论文完整列表（精简版）`
   - Use a compact table with `#`, `arXiv ID`, `标题（简）`, `类别`, `相关度`, `推荐度`, and `关系`.
   - Include all selected and borderline papers worth tracking.
   - Do not dump hundreds of clearly unrelated candidates; summarize the remaining non-relevant papers in one sentence.
6. `## 方法论注记`
   - State the arXiv API date range, focus categories, candidate count, and that the executing AI assistant evaluated titles, abstracts, categories, and metadata.
   - State that the report is not exhaustive citation coverage.

## Script Options

Use `scripts/fetch_related_arxiv.py` for arXiv API fetching and packet generation. The script does not call an LLM API and does not require an AI provider API key.

Important options:

- `--ids`: Required seed arXiv IDs, comma-separated or space-separated.
- `--config`: Optional JSON config file. Supported keys: `categories`, `focus_categories`, `include_categories`, `exclude_categories`, `excluded_categories`. When omitted, auto-checks `~/.arxiv-weekly-related-papers/config.json` and then `~/.arxiv-weekly-related-papers/arxiv_weekly_config.json`.
- `--packet-output`: Markdown packet path for the executing AI assistant to read. Defaults to `arxiv_candidate_packet_<date>.md`.
- `--json-output`: Optional JSON packet path with the same papers and metadata.
- `--days`: Lookback window in UTC days. Defaults to `7`.
- `--start-date`, `--end-date`: Explicit UTC date range, inclusive.
- `--categories`: Comma-separated arXiv focus categories. Overrides config categories. Defaults to `hep-ex,nucl-ex,hep-ph,nucl-th`.
- `--exclude-categories`: Comma-separated arXiv categories to omit before packet generation. Overrides config exclude categories.
- `--date-field`: `lastUpdatedDate` or `submittedDate`. Defaults to `lastUpdatedDate`.
- `--max-candidates`: Maximum recent category papers fetched into the packet. Defaults to `1000`.
- `--batch-size`: Number of candidate papers per Markdown batch. Defaults to `20`.
- `--language`: `zh` or `en` for packet instructions. Defaults to `zh`.

If network access is blocked by the execution environment, request approval to rerun the script with network access rather than fabricating results. The script only requires access to `export.arxiv.org`.

## Output Expectations

The Markdown report should include:

- Query parameters and date range.
- Focus categories, excluded categories, and counts of candidates removed before AI analysis.
- Seed paper metadata.
- AI-selected papers with arXiv ID, title, categories, authors, dates, relevance score, recommendation score, relation type, reasoning, links, and research-extension ideas.
- A complete list or compact appendix of all evaluated candidate papers.
- A "no results" note when no candidate is worth recommending.
- A short methodology note explaining that the arXiv script only fetched metadata and the executing AI assistant evaluated the abstracts.
