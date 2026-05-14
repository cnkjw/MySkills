#!/usr/bin/env python3
"""Fetch recent arXiv papers and write an AI-readable analysis packet."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_CATEGORIES = ("hep-ex", "nucl-ex", "hep-ph", "nucl-th")
DEFAULT_CONFIG_DIR = Path("~/.arxiv-weekly-related-papers").expanduser()
DEFAULT_CONFIG_FILENAMES = ("config.json", "arxiv_weekly_config.json")
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


@dataclass(frozen=True)
class Paper:
    arxiv_id: str
    versioned_id: str
    title: str
    summary: str
    authors: tuple[str, ...]
    published: str
    updated: str
    primary_category: str
    categories: tuple[str, ...]
    abs_url: str
    pdf_url: str
    doi: str = ""
    journal_ref: str = ""
    comment: str = ""


def normalize_id(raw: str, keep_version: bool = False) -> str:
    value = raw.strip()
    value = re.sub(r"^https?://arxiv\.org/(abs|pdf)/", "", value, flags=re.I)
    value = re.sub(r"\.pdf$", "", value, flags=re.I)
    value = re.sub(r"^arxiv:", "", value, flags=re.I)
    value = value.strip()
    if not keep_version:
        value = re.sub(r"v\d+$", "", value, flags=re.I)
    return value


def split_csv_or_space(values: list[str]) -> list[str]:
    items: list[str] = []
    for value in values:
        items.extend(part.strip() for part in value.split(","))
    return [item for item in items if item]


def parse_ymd(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date '{value}', expected YYYY-MM-DD") from exc


def default_config_candidates() -> list[Path]:
    return [DEFAULT_CONFIG_DIR / filename for filename in DEFAULT_CONFIG_FILENAMES]


def find_config_path(explicit_path: Path | None) -> Path | None:
    if explicit_path is not None:
        return explicit_path.expanduser()
    for path in default_config_candidates():
        if path.exists():
            return path
    return None


def load_config(path: Path | None) -> tuple[dict[str, Any], Path | None]:
    resolved_path = find_config_path(path)
    if resolved_path is None:
        return {}, None
    try:
        data = json.loads(resolved_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Config file not found: {resolved_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config file {resolved_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Config file must contain a JSON object: {resolved_path}")
    return data, resolved_path


def config_value(config: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in config:
            return config[key]
    return None


def categories_from_value(value: Any, *, option_name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return split_csv_or_space([value])
    if isinstance(value, list):
        categories: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise SystemExit(f"{option_name} must contain only category strings.")
            categories.extend(split_csv_or_space([item]))
        return categories
    raise SystemExit(f"{option_name} must be a comma-separated string or a list of strings.")


def resolve_categories(cli_value: str | None, config: dict[str, Any]) -> list[str]:
    if cli_value is not None:
        categories = categories_from_value(cli_value, option_name="--categories")
    else:
        categories = categories_from_value(
            config_value(config, "categories", "focus_categories", "include_categories"),
            option_name="config categories",
        )
    return categories or list(DEFAULT_CATEGORIES)


def resolve_exclude_categories(cli_value: str | None, config: dict[str, Any]) -> list[str]:
    if cli_value is not None:
        return categories_from_value(cli_value, option_name="--exclude-categories")
    return categories_from_value(
        config_value(config, "exclude_categories", "excluded_categories"),
        option_name="config exclude_categories",
    )


def arxiv_api_get(params: dict[str, str | int]) -> ET.Element:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{ARXIV_API_URL}?{query}",
        headers={"User-Agent": "codex-arxiv-weekly-related-papers/3.0"},
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 503} or attempt == 3:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = int(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1)
            print(f"arXiv API returned HTTP {exc.code}; retrying in {delay}s...", file=sys.stderr)
            time.sleep(delay)
    return ET.fromstring(payload)


def text_of(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(element.text)).strip()


def parse_paper(entry: ET.Element) -> Paper:
    abs_url = text_of(entry.find(f"{ATOM}id"))
    versioned_id = normalize_id(abs_url.rsplit("/", 1)[-1], keep_version=True)
    arxiv_id = normalize_id(versioned_id)
    links = entry.findall(f"{ATOM}link")
    pdf_url = ""
    for link in links:
        if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
            pdf_url = link.attrib.get("href", "")
            break
    primary = entry.find(f"{ARXIV}primary_category")
    categories = tuple(
        category.attrib.get("term", "")
        for category in entry.findall(f"{ATOM}category")
        if category.attrib.get("term")
    )
    authors = tuple(
        text_of(author.find(f"{ATOM}name"))
        for author in entry.findall(f"{ATOM}author")
        if text_of(author.find(f"{ATOM}name"))
    )
    return Paper(
        arxiv_id=arxiv_id,
        versioned_id=versioned_id,
        title=text_of(entry.find(f"{ATOM}title")),
        summary=text_of(entry.find(f"{ATOM}summary")),
        authors=authors,
        published=text_of(entry.find(f"{ATOM}published")),
        updated=text_of(entry.find(f"{ATOM}updated")),
        primary_category=primary.attrib.get("term", "") if primary is not None else "",
        categories=categories,
        abs_url=abs_url or f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=pdf_url or f"https://arxiv.org/pdf/{arxiv_id}",
        doi=text_of(entry.find(f"{ARXIV}doi")),
        journal_ref=text_of(entry.find(f"{ARXIV}journal_ref")),
        comment=text_of(entry.find(f"{ARXIV}comment")),
    )


def entries_from_feed(feed: ET.Element) -> list[Paper]:
    return [parse_paper(entry) for entry in feed.findall(f"{ATOM}entry")]


def fetch_seed_papers(ids: list[str]) -> list[Paper]:
    versioned = [normalize_id(item, keep_version=True) for item in ids]
    feed = arxiv_api_get({"id_list": ",".join(versioned), "max_results": len(versioned)})
    papers = entries_from_feed(feed)
    found = {paper.arxiv_id for paper in papers}
    missing = [normalize_id(item) for item in ids if normalize_id(item) not in found]
    if missing:
        print(f"Warning: seed IDs not found in arXiv API: {', '.join(missing)}", file=sys.stderr)
    return papers


def date_query(start_date: dt.date, end_date: dt.date) -> str:
    start = start_date.strftime("%Y%m%d") + "0000"
    end = end_date.strftime("%Y%m%d") + "2359"
    return f"submittedDate:[{start} TO {end}]"


def paper_window_date(paper: Paper, date_field: str) -> dt.date | None:
    value = paper.updated if date_field == "lastUpdatedDate" else paper.published
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def fetch_recent_candidates(
    categories: list[str],
    start_date: dt.date,
    end_date: dt.date,
    date_field: str,
    max_candidates: int,
    page_size: int,
) -> list[Paper]:
    category_query = " OR ".join(f"cat:{category}" for category in categories)
    search_query = f"({category_query})"
    if date_field == "submittedDate":
        search_query = f"{search_query} AND {date_query(start_date, end_date)}"

    papers: list[Paper] = []
    seen: set[str] = set()
    for start in range(0, max_candidates, page_size):
        limit = min(page_size, max_candidates - start)
        feed = arxiv_api_get(
            {
                "search_query": search_query,
                "start": start,
                "max_results": limit,
                "sortBy": date_field,
                "sortOrder": "descending",
            }
        )
        page = entries_from_feed(feed)
        if not page:
            break
        saw_older_update = False
        for paper in page:
            window_date = paper_window_date(paper, date_field)
            if window_date is None:
                continue
            if date_field == "lastUpdatedDate" and window_date < start_date:
                saw_older_update = True
                continue
            if start_date <= window_date <= end_date and paper.arxiv_id not in seen:
                papers.append(paper)
                seen.add(paper.arxiv_id)
                if len(papers) >= max_candidates:
                    return papers
        if len(page) < limit:
            break
        if date_field == "lastUpdatedDate" and saw_older_update:
            break
        time.sleep(3.0)
    return papers


def short_authors(authors: tuple[str, ...], limit: int = 8) -> str:
    if len(authors) <= limit:
        return ", ".join(authors)
    return ", ".join(authors[:limit]) + f", et al. ({len(authors)} authors)"


def chunked(items: list[Paper], size: int) -> list[list[Paper]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def paper_as_jsonable(paper: Paper) -> dict[str, Any]:
    data = asdict(paper)
    data["authors"] = list(paper.authors)
    data["categories"] = list(paper.categories)
    return data


def excluded_category_hits(paper: Paper, exclude_categories: set[str]) -> list[str]:
    if not exclude_categories:
        return []
    return sorted(set(paper.categories) & exclude_categories)


def filter_excluded_categories(
    candidates: list[Paper],
    exclude_categories: list[str],
) -> tuple[list[Paper], int, dict[str, int]]:
    exclude_set = set(exclude_categories)
    kept: list[Paper] = []
    excluded_paper_count = 0
    excluded_counts: dict[str, int] = {}
    for paper in candidates:
        hits = excluded_category_hits(paper, exclude_set)
        if hits:
            excluded_paper_count += 1
            for category in hits:
                excluded_counts[category] = excluded_counts.get(category, 0) + 1
            continue
        kept.append(paper)
    return kept, excluded_paper_count, dict(sorted(excluded_counts.items()))


def write_json_packet(
    output: Path,
    *,
    seeds: list[Paper],
    candidates: list[Paper],
    categories: list[str],
    exclude_categories: list[str],
    excluded_paper_count: int,
    excluded_counts: dict[str, int],
    config_path: Path | None,
    start_date: dt.date,
    end_date: dt.date,
    date_field: str,
) -> None:
    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "config_path": str(config_path) if config_path else None,
        "date_field": date_field,
        "date_range": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "timezone": "UTC",
        },
        "focus_categories": categories,
        "exclude_categories": exclude_categories,
        "excluded_candidate_count": excluded_paper_count,
        "excluded_counts_by_category": excluded_counts,
        "seed_papers": [paper_as_jsonable(paper) for paper in seeds],
        "candidate_papers": [paper_as_jsonable(paper) for paper in candidates],
        "analysis_schema": {
            "relevance_score": "0-100 topical or methodological relatedness to the seed papers",
            "recommendation_score": "0-100 how strongly the research group should read or track the paper",
            "relation_type": "direct | method | background | contrast | weak | not_related",
            "research_ideas": "Concrete follow-up directions or ways to connect the candidate paper with the seed-paper research",
        },
        "preferred_final_report_format": [
            "Title: arXiv weekly report mentioning seed count or main seed topic",
            "Query parameters: use bold Chinese labels in this exact order: 生成时间, 日期范围, 日期字段, 关注类别, 排除类别, 候选论文总数, AI 分析前排除; fill values dynamically from this packet; use Chinese full-width colon",
            "Seed paper overview: group seed papers into research subdirections and summarize their core content/methods in tables",
            "AI-selected papers: group by relation type in this order: direct, method, background, weak",
            "Selected paper entries: include title, then Chinese metadata bullets for 作者, 类别, 发表/更新, 相关度评分, 推荐度评分, 关系类型, followed by relevance reason, recommendation reason, and research ideas",
            "Compact candidate table: include only evaluated papers worth listing, with arXiv ID, short title, categories, relevance score, recommendation score, and relation",
            "Methodology note: state that arXiv API fetched candidates and the executing AI assistant evaluated titles, abstracts, categories, and metadata",
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown_packet(
    output: Path,
    *,
    seeds: list[Paper],
    candidates: list[Paper],
    categories: list[str],
    exclude_categories: list[str],
    excluded_paper_count: int,
    excluded_counts: dict[str, int],
    config_path: Path | None,
    start_date: dt.date,
    end_date: dt.date,
    date_field: str,
    batch_size: int,
    language: str,
) -> None:
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if language == "zh":
        title = "arXiv 候选论文 AI 分析包"
        instruction = (
            "执行该 skill 的 Codex/opencode/Claude Code 应读取本文件，基于种子论文摘要分析每篇候选论文。"
            "不要使用本地关键词/分类/作者重合打分；用当前模型判断相关程度、推荐程度，并为值得关注的论文给出拓展研究思路。"
        )
        meta_labels = {
            "authors": "作者",
            "categories": "类别",
            "published": "发表",
            "updated": "更新",
            "pdf": "PDF",
        }
    else:
        title = "arXiv Candidate Packet for AI Analysis"
        instruction = (
            "The Codex/opencode/Claude Code agent executing this skill should read this packet and analyze every candidate "
            "against the seed-paper abstracts. Do not use local keyword/category/author-overlap scoring; use the current "
            "model to judge relevance, recommendation strength, and extension ideas for useful papers."
        )
        meta_labels = {
            "authors": "Authors",
            "categories": "Categories",
            "published": "Published",
            "updated": "Updated",
            "pdf": "PDF",
        }

    lines = [
        f"# {title}",
        "",
        instruction,
        "",
        "## Query",
        "",
        f"- Generated: {generated}",
        f"- Config: {config_path if config_path else 'none'}",
        f"- Date field: {date_field}",
        f"- Date range: {start_date.isoformat()} to {end_date.isoformat()} (UTC, inclusive)",
        f"- Focus categories: {', '.join(categories)}",
        f"- Exclude categories: {', '.join(exclude_categories) if exclude_categories else 'none'}",
        f"- Seed IDs: {', '.join(paper.arxiv_id for paper in seeds)}",
        f"- Candidate count: {len(candidates)}",
        f"- Excluded before AI analysis: {excluded_paper_count}",
        "",
        "## Required AI Output Fields",
        "",
        "- `relevance_score`: 0-100",
        "- `recommendation_score`: 0-100",
        "- `relation_type`: direct | method | background | contrast | weak | not_related",
        "- `relevance_reason`: concise reason grounded in the abstracts",
        "- `recommendation_reason`: why the group should or should not track it",
        "- `research_ideas`: concrete extension ideas or ways to combine with the seed-paper research",
        "",
        "## Preferred Final Report Format",
        "",
        "Use this structure for the final Markdown report unless the user asks for another style:",
        "",
        "1. `# arXiv 周报：<种子数量或核心主题>相关候选分析`",
        "2. `## 查询参数`: use exactly this field order and label style. Fill values dynamically from this packet; do not copy placeholder values:",
        "   - `- **生成时间**：<generated time>`",
        "   - `- **日期范围**：<start date> 至 <end date>（UTC，含端点）`",
        "   - `- **日期字段**：<date_field>`",
        "   - `- **关注类别**：<focus categories joined by \", \">`",
        "   - `- **排除类别**：<exclude categories joined by \", \" or \"无\">`",
        "   - `- **候选论文总数**：<candidate paper count>`",
        "   - `- **AI 分析前排除**：<excluded candidate count>`",
        "3. `## 种子论文概览`: group seed papers into 2-4 research subdirections; use compact tables with arXiv ID, core content, and method.",
        "4. `## AI 精选论文`: group selected papers by relation type in this order: `direct`, `method`, `background`, `weak`.",
        "5. For every selected paper, use a numbered `####` heading. Under it, use exactly these Chinese metadata bullets: `- **作者**：...`, `- **类别**：...`, `- **发表/更新**：...`, `- **相关度评分**：.../100`, `- **推荐度评分**：.../100`, `- **关系类型**：...`. Do not use English metadata labels or semicolon-separated inline metadata. Then include relevance reason, recommendation reason, and concrete research ideas.",
        "6. `## 候选论文完整列表（精简版）`: use a compact table with arXiv ID, short title, categories, relevance score, recommendation score, and relation. Do not dump hundreds of unrelated rows; summarize the remaining non-relevant papers in one sentence.",
        "7. `## 方法论注记`: state that candidates came from arXiv API and were evaluated by the executing AI assistant from titles, abstracts, categories, and metadata. Do not claim exhaustive citation coverage.",
        "",
    ]
    if excluded_counts:
        lines.extend(["## Excluded Category Hits", ""])
        for category, count in excluded_counts.items():
            lines.append(f"- {category}: {count}")
        lines.extend(["", "Excluded papers are intentionally omitted from this packet to save model context.", ""])

    lines.extend(["## Seed Papers", ""])

    for paper in seeds:
        lines.extend(
            [
                f"### [{paper.arxiv_id}]({paper.abs_url}) {paper.title}",
                "",
                f"- {meta_labels['authors']}: {short_authors(paper.authors)}",
                f"- {meta_labels['categories']}: {', '.join(paper.categories)}",
                f"- {meta_labels['published']}: {paper.published[:10]}",
                f"- {meta_labels['updated']}: {paper.updated[:10]}",
                f"- {meta_labels['pdf']}: {paper.pdf_url}",
                "",
                paper.summary,
                "",
            ]
        )

    lines.extend(["## Candidate Papers", ""])
    if not candidates:
        lines.extend(["No candidate papers remain after seed-paper and excluded-category filtering.", ""])
    for batch_index, batch in enumerate(chunked(candidates, batch_size), 1):
        lines.extend([f"### Batch {batch_index}", ""])
        for paper in batch:
            lines.extend(
                [
                    f"#### [{paper.arxiv_id}]({paper.abs_url}) {paper.title}",
                    "",
                    f"- {meta_labels['authors']}: {short_authors(paper.authors)}",
                    f"- {meta_labels['categories']}: {', '.join(paper.categories)}",
                    f"- {meta_labels['published']}: {paper.published[:10]}",
                    f"- {meta_labels['updated']}: {paper.updated[:10]}",
                    f"- {meta_labels['pdf']}: {paper.pdf_url}",
                    "",
                    paper.summary,
                    "",
                ]
            )
            if paper.comment:
                lines.extend([f"- Comment: {paper.comment}", ""])
            if paper.journal_ref:
                lines.extend([f"- Journal ref: {paper.journal_ref}", ""])
            if paper.doi:
                lines.extend([f"- DOI: {paper.doi}", ""])

    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        help=(
            "Optional JSON config file for focus and exclude categories. "
            "When omitted, the script checks ~/.arxiv-weekly-related-papers/config.json "
            "then ~/.arxiv-weekly-related-papers/arxiv_weekly_config.json."
        ),
    )
    parser.add_argument("--ids", nargs="+", required=True, help="Seed arXiv IDs, comma-separated or space-separated.")
    parser.add_argument("--packet-output", type=Path, help="Markdown packet path for the executing AI agent to read.")
    parser.add_argument("--json-output", type=Path, help="Optional JSON packet path with the same papers and metadata.")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in UTC days when explicit dates are absent.")
    parser.add_argument("--start-date", type=parse_ymd, help="Inclusive UTC start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", type=parse_ymd, help="Inclusive UTC end date, YYYY-MM-DD.")
    parser.add_argument("--categories", help="Comma-separated arXiv focus categories. Overrides config categories.")
    parser.add_argument(
        "--exclude-categories",
        help="Comma-separated arXiv categories to drop before packet generation. Overrides config exclude_categories.",
    )
    parser.add_argument(
        "--date-field",
        choices=("lastUpdatedDate", "submittedDate"),
        default="lastUpdatedDate",
        help="arXiv date field used for the one-week window and sorting.",
    )
    parser.add_argument("--max-candidates", type=int, default=1000, help="Maximum recent category papers to fetch.")
    parser.add_argument("--page-size", type=int, default=100, help="arXiv API page size.")
    parser.add_argument("--batch-size", type=int, default=20, help="Number of candidate papers per Markdown batch.")
    parser.add_argument("--language", choices=("zh", "en"), default="zh", help="Packet instruction language.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    config, config_path = load_config(args.config)
    seed_ids = split_csv_or_space(args.ids)
    if not seed_ids:
        raise SystemExit("At least one seed arXiv ID is required.")
    categories = resolve_categories(args.categories, config)
    exclude_categories = resolve_exclude_categories(args.exclude_categories, config)
    if not categories:
        raise SystemExit("At least one arXiv category is required.")
    if args.days <= 0:
        raise SystemExit("--days must be positive.")
    if args.max_candidates <= 0:
        raise SystemExit("--max-candidates must be positive.")
    if args.page_size <= 0 or args.page_size > 2000:
        raise SystemExit("--page-size must be between 1 and 2000.")
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be positive.")

    today = dt.datetime.now(dt.timezone.utc).date()
    end_date = args.end_date or today
    start_date = args.start_date or (end_date - dt.timedelta(days=args.days - 1))
    if start_date > end_date:
        raise SystemExit("--start-date must be on or before --end-date.")

    packet_output = args.packet_output or Path(f"arxiv_candidate_packet_{end_date.isoformat()}.md")
    json_output = args.json_output

    print(f"Fetching seed metadata for {len(seed_ids)} ID(s)...", file=sys.stderr)
    seeds = fetch_seed_papers(seed_ids)
    if not seeds:
        raise SystemExit("No seed papers were found; cannot build an analysis packet.")

    print(
        f"Fetching recent candidates in {', '.join(categories)} from {start_date} to {end_date}...",
        file=sys.stderr,
    )
    candidates = fetch_recent_candidates(
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        date_field=args.date_field,
        max_candidates=args.max_candidates,
        page_size=args.page_size,
    )
    seed_arxiv_ids = {paper.arxiv_id for paper in seeds}
    candidates = [paper for paper in candidates if paper.arxiv_id not in seed_arxiv_ids]
    candidates, excluded_paper_count, excluded_counts = filter_excluded_categories(candidates, exclude_categories)

    write_markdown_packet(
        packet_output,
        seeds=seeds,
        candidates=candidates,
        categories=categories,
        exclude_categories=exclude_categories,
        excluded_paper_count=excluded_paper_count,
        excluded_counts=excluded_counts,
        config_path=config_path,
        start_date=start_date,
        end_date=end_date,
        date_field=args.date_field,
        batch_size=args.batch_size,
        language=args.language,
    )
    if json_output:
        write_json_packet(
            json_output,
            seeds=seeds,
            candidates=candidates,
            categories=categories,
            exclude_categories=exclude_categories,
            excluded_paper_count=excluded_paper_count,
            excluded_counts=excluded_counts,
            config_path=config_path,
            start_date=start_date,
            end_date=end_date,
            date_field=args.date_field,
        )
    print(f"Wrote {packet_output} with {len(candidates)} candidate paper(s).", file=sys.stderr)
    if excluded_paper_count:
        print(f"Excluded {excluded_paper_count} candidate paper(s) by category.", file=sys.stderr)
    if json_output:
        print(f"Wrote {json_output}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
