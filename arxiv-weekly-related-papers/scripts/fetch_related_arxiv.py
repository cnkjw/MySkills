#!/usr/bin/env python3
"""Fetch recent arXiv papers related to seed IDs and write a Markdown report."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import math
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


API_URL = "https://export.arxiv.org/api/query"
DEFAULT_CATEGORIES = ("hep-ex", "nucl-ex", "hep-ph", "nucl-th")
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"

STOPWORDS = {
    "about", "above", "after", "again", "against", "all", "also", "and", "any",
    "are", "because", "been", "being", "between", "both", "can", "could",
    "did", "does", "doing", "done", "due", "each", "for", "from", "had",
    "has", "have", "having", "here", "how", "into", "its", "itself", "may",
    "more", "most", "much", "not", "our", "out", "over", "same", "should",
    "show", "shown", "such", "than", "that", "the", "their", "then", "there",
    "these", "this", "those", "through", "under", "using", "was", "were",
    "when", "where", "which", "while", "with", "within", "would",
    "study", "studies", "paper", "results", "result", "analysis", "data",
    "measurement", "measurements", "model", "models", "new", "using",
}


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


@dataclass(frozen=True)
class ScoredPaper:
    paper: Paper
    score: float
    matched_keywords: tuple[str, ...]
    shared_authors: tuple[str, ...]
    shared_categories: tuple[str, ...]


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


def api_get(params: dict[str, str | int]) -> ET.Element:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{API_URL}?{query}",
        headers={"User-Agent": "codex-arxiv-weekly-related-papers/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = response.read()
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
    doi = text_of(entry.find(f"{ARXIV}doi"))
    journal_ref = text_of(entry.find(f"{ARXIV}journal_ref"))
    comment = text_of(entry.find(f"{ARXIV}comment"))
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
        doi=doi,
        journal_ref=journal_ref,
        comment=comment,
    )


def entries_from_feed(feed: ET.Element) -> list[Paper]:
    return [parse_paper(entry) for entry in feed.findall(f"{ATOM}entry")]


def fetch_seed_papers(ids: list[str]) -> list[Paper]:
    versioned = [normalize_id(item, keep_version=True) for item in ids]
    feed = api_get({"id_list": ",".join(versioned), "max_results": len(versioned)})
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


def fetch_recent_candidates(
    categories: list[str],
    start_date: dt.date,
    end_date: dt.date,
    max_candidates: int,
    page_size: int,
) -> list[Paper]:
    category_query = " OR ".join(f"cat:{category}" for category in categories)
    search_query = f"({category_query}) AND {date_query(start_date, end_date)}"
    papers: list[Paper] = []
    seen: set[str] = set()
    for start in range(0, max_candidates, page_size):
        limit = min(page_size, max_candidates - start)
        feed = api_get(
            {
                "search_query": search_query,
                "start": start,
                "max_results": limit,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            }
        )
        page = entries_from_feed(feed)
        if not page:
            break
        for paper in page:
            if paper.arxiv_id not in seen:
                papers.append(paper)
                seen.add(paper.arxiv_id)
        if len(page) < limit:
            break
        time.sleep(3.0)
    return papers


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+\-]{2,}", text.lower())
    normalized = [token.strip("-") for token in tokens]
    return [token for token in normalized if len(token) >= 3 and token not in STOPWORDS]


def author_key(name: str) -> str:
    parts = re.findall(r"[A-Za-z]+", name.lower())
    if not parts:
        return ""
    return parts[-1]


def seed_profile(seed_papers: list[Paper]) -> tuple[Counter[str], set[str], set[str]]:
    weighted_terms: Counter[str] = Counter()
    authors: set[str] = set()
    categories: set[str] = set()
    for paper in seed_papers:
        weighted_terms.update({token: 4 for token in tokenize(paper.title)})
        weighted_terms.update(tokenize(paper.summary))
        authors.update(key for key in (author_key(author) for author in paper.authors) if key)
        categories.update(paper.categories)
        if paper.primary_category:
            categories.add(paper.primary_category)
    return weighted_terms, authors, categories


def score_candidate(paper: Paper, terms: Counter[str], seed_authors: set[str], seed_categories: set[str]) -> ScoredPaper:
    candidate_title = set(tokenize(paper.title))
    candidate_summary = set(tokenize(paper.summary))
    candidate_terms = candidate_title | candidate_summary
    top_seed_terms = {term for term, _ in terms.most_common(120)}
    matched = sorted(top_seed_terms & candidate_terms, key=lambda term: (-terms[term], term))

    title_hits = candidate_title & top_seed_terms
    summary_hits = candidate_summary & top_seed_terms
    category_hits = sorted(set(paper.categories) & seed_categories)
    paper_authors = {key for key in (author_key(author) for author in paper.authors) if key}
    author_hits = sorted(paper_authors & seed_authors)

    keyword_score = sum(1.0 + math.log1p(terms[token]) for token in summary_hits)
    title_score = sum(2.0 + math.log1p(terms[token]) for token in title_hits)
    category_score = 1.5 * len(category_hits)
    author_score = 2.0 * len(author_hits)
    score = title_score + keyword_score + category_score + author_score

    return ScoredPaper(
        paper=paper,
        score=round(score, 2),
        matched_keywords=tuple(matched[:12]),
        shared_authors=tuple(author_hits[:8]),
        shared_categories=tuple(category_hits),
    )


def rank_candidates(
    seeds: list[Paper],
    candidates: list[Paper],
    min_score: float,
    top_n: int,
) -> list[ScoredPaper]:
    seed_ids = {paper.arxiv_id for paper in seeds}
    terms, seed_authors, seed_categories = seed_profile(seeds)
    scored = [
        score_candidate(paper, terms, seed_authors, seed_categories)
        for paper in candidates
        if paper.arxiv_id not in seed_ids
    ]
    filtered = [item for item in scored if item.score >= min_score]
    filtered.sort(key=lambda item: (-item.score, item.paper.published, item.paper.arxiv_id))
    return filtered[:top_n]


def md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def short_authors(authors: tuple[str, ...], limit: int = 8) -> str:
    if len(authors) <= limit:
        return ", ".join(authors)
    return ", ".join(authors[:limit]) + f", et al. ({len(authors)} authors)"


def first_paragraph(text: str, max_chars: int = 700) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 1].rstrip() + "..."


def labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "title": "arXiv Related Papers Report",
            "params": "Query Parameters",
            "seeds": "Seed Papers",
            "related": "Ranked Related Papers",
            "none": "No candidate papers met the score threshold.",
            "method": "Methodology",
            "abstract": "Abstract",
            "score": "Score",
            "keywords": "Matched keywords",
            "shared_authors": "Shared author surnames",
            "shared_categories": "Shared categories",
            "links": "Links",
        }
    return {
        "title": "arXiv 相关文献周报",
        "params": "查询参数",
        "seeds": "种子论文",
        "related": "相关文献排序",
        "none": "没有候选论文达到相关性分数阈值。",
        "method": "方法说明",
        "abstract": "摘要",
        "score": "相关性分数",
        "keywords": "匹配关键词",
        "shared_authors": "共享作者姓氏",
        "shared_categories": "共享分类",
        "links": "链接",
    }


def write_report(
    output: Path,
    seeds: list[Paper],
    ranked: list[ScoredPaper],
    categories: list[str],
    start_date: dt.date,
    end_date: dt.date,
    args: argparse.Namespace,
) -> None:
    text = labels(args.language)
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# {text['title']}",
        "",
        f"- Generated: {generated}",
        f"- Date range: {start_date.isoformat()} to {end_date.isoformat()} (UTC, inclusive)",
        f"- Categories: {', '.join(categories)}",
        f"- Seed IDs: {', '.join(paper.arxiv_id for paper in seeds)}",
        f"- Candidates fetched: up to {args.max_candidates}",
        f"- Minimum score: {args.min_score}",
        "",
        f"## {text['seeds']}",
        "",
    ]

    for paper in seeds:
        lines.extend(
            [
                f"### [{paper.arxiv_id}]({paper.abs_url}) {paper.title}",
                "",
                f"- Authors: {short_authors(paper.authors)}",
                f"- Categories: {', '.join(paper.categories)}",
                f"- Published: {paper.published[:10]}",
                f"- Updated: {paper.updated[:10]}",
                f"- PDF: {paper.pdf_url}",
                "",
                f"{first_paragraph(paper.summary)}",
                "",
            ]
        )

    lines.extend([f"## {text['related']}", ""])
    if not ranked:
        lines.extend([text["none"], ""])
    for index, item in enumerate(ranked, 1):
        paper = item.paper
        lines.extend(
            [
                f"### {index}. [{paper.arxiv_id}]({paper.abs_url}) {paper.title}",
                "",
                f"- {text['score']}: {item.score}",
                f"- Authors: {short_authors(paper.authors)}",
                f"- Categories: {', '.join(paper.categories)}",
                f"- Published: {paper.published[:10]}",
                f"- Updated: {paper.updated[:10]}",
                f"- {text['keywords']}: {', '.join(item.matched_keywords) if item.matched_keywords else 'n/a'}",
                f"- {text['shared_authors']}: {', '.join(item.shared_authors) if item.shared_authors else 'n/a'}",
                f"- {text['shared_categories']}: {', '.join(item.shared_categories) if item.shared_categories else 'n/a'}",
                f"- {text['links']}: [abs]({paper.abs_url}), [pdf]({paper.pdf_url})",
                "",
                f"**{text['abstract']}:** {first_paragraph(paper.summary)}",
                "",
            ]
        )
        if paper.comment:
            lines.extend([f"- Comment: {md_escape(paper.comment)}", ""])
        if paper.journal_ref:
            lines.extend([f"- Journal ref: {md_escape(paper.journal_ref)}", ""])
        if paper.doi:
            lines.extend([f"- DOI: {md_escape(paper.doi)}", ""])

    methodology = (
        "This report uses the public arXiv API. Recent papers are fetched by submittedDate "
        "and category, then ranked with a heuristic score based on overlap with seed-paper "
        "title terms, abstract terms, arXiv categories, and author surnames. arXiv does not "
        "provide a native related-paper endpoint, so rankings are candidates for review rather "
        "than exhaustive citation or semantic-similarity results."
    )
    if args.language == "zh":
        methodology = (
            "本报告使用公开 arXiv API。脚本先按 submittedDate 与分类抓取近期论文，"
            "再根据种子论文标题词、摘要词、arXiv 分类和作者姓氏重合度进行启发式排序。"
            "arXiv 不提供原生 related-paper 端点，因此结果是供人工复核的候选列表，"
            "不是穷尽式引文检索或语义相似度检索。"
        )
    lines.extend([f"## {text['method']}", "", methodology, ""])
    output.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="+", required=True, help="Seed arXiv IDs, comma-separated or space-separated.")
    parser.add_argument("--output", type=Path, help="Markdown output path.")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in UTC days when explicit dates are absent.")
    parser.add_argument("--start-date", type=parse_ymd, help="Inclusive UTC start date, YYYY-MM-DD.")
    parser.add_argument("--end-date", type=parse_ymd, help="Inclusive UTC end date, YYYY-MM-DD.")
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES), help="Comma-separated arXiv categories.")
    parser.add_argument("--max-candidates", type=int, default=1000, help="Maximum recent category papers to fetch.")
    parser.add_argument("--page-size", type=int, default=100, help="arXiv API page size.")
    parser.add_argument("--top-n", type=int, default=50, help="Maximum related papers to include.")
    parser.add_argument("--min-score", type=float, default=2.5, help="Minimum relatedness score.")
    parser.add_argument("--language", choices=("zh", "en"), default="zh", help="Report label language.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    seed_ids = split_csv_or_space(args.ids)
    if not seed_ids:
        raise SystemExit("At least one seed arXiv ID is required.")
    categories = split_csv_or_space([args.categories])
    if not categories:
        raise SystemExit("At least one arXiv category is required.")
    if args.days <= 0:
        raise SystemExit("--days must be positive.")
    if args.max_candidates <= 0:
        raise SystemExit("--max-candidates must be positive.")
    if args.page_size <= 0 or args.page_size > 2000:
        raise SystemExit("--page-size must be between 1 and 2000.")

    today = dt.datetime.now(dt.timezone.utc).date()
    end_date = args.end_date or today
    start_date = args.start_date or (end_date - dt.timedelta(days=args.days - 1))
    if start_date > end_date:
        raise SystemExit("--start-date must be on or before --end-date.")

    output = args.output or Path(f"arxiv_related_{end_date.isoformat()}.md")

    print(f"Fetching seed metadata for {len(seed_ids)} ID(s)...", file=sys.stderr)
    seeds = fetch_seed_papers(seed_ids)
    if not seeds:
        raise SystemExit("No seed papers were found; cannot build a related-paper profile.")

    print(
        f"Fetching recent candidates in {', '.join(categories)} from {start_date} to {end_date}...",
        file=sys.stderr,
    )
    candidates = fetch_recent_candidates(
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        max_candidates=args.max_candidates,
        page_size=args.page_size,
    )
    ranked = rank_candidates(seeds, candidates, min_score=args.min_score, top_n=args.top_n)
    write_report(output, seeds, ranked, categories, start_date, end_date, args)
    print(f"Wrote {output} with {len(ranked)} related paper(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
