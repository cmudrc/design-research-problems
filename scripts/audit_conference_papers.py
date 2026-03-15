"""Scan conference PDFs for optimization and grammar-based problem candidates."""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFERENCES_ROOT = REPO_ROOT / "conferences"
DEFAULT_OUTPUT_CSV = REPO_ROOT / "artifacts" / "conference_problem_scan.csv"

OPTIMIZATION_PHRASES: tuple[tuple[str, int], ...] = (
    ("subject to", 4),
    ("design variables", 4),
    ("design variable", 4),
    ("objective function", 4),
    ("decision variables", 4),
    ("multi-objective", 4),
    ("multiobjective", 4),
    ("optimization", 3),
    ("optimisation", 3),
    ("optimize", 3),
    ("optimizing", 3),
    ("pareto", 2),
    ("constraint", 2),
    ("minimize", 2),
    ("maximize", 2),
    ("minimization", 2),
    ("maximization", 2),
)

GRAMMAR_PHRASES: tuple[tuple[str, int], ...] = (
    ("graph grammar", 6),
    ("shape grammar", 6),
    ("spatial grammar", 5),
    ("generative grammar", 5),
    ("production rule", 4),
    ("production rules", 4),
    ("rewrite rule", 4),
    ("rewrite rules", 4),
    ("rule-based grammar", 4),
    ("graph-rewriting", 4),
    ("graph rewriting", 4),
    ("grammar", 2),
    ("generative rules", 2),
)

TITLE_SKIP_PREFIXES = (
    "proceedings of",
    "copyright",
    "downloaded from",
    "page ",
    "doi:",
    "doi ",
    "asme",
    "the design society",
)

TITLE_SKIP_CONTAINS = (
    "@",
    "conference",
    "http://",
    "https://",
    "all rights reserved",
)

PAPER_MARKER_PATTERN = re.compile(r"^(DETC|IMECE|ICED|DCC|CMMI|ASME)\w*[-' ]?\d", re.IGNORECASE)


@dataclass(frozen=True)
class ScanResult:
    relative_path: str
    venue: str
    title: str
    optimization_score: int
    grammar_score: int
    optimization_hits: str
    grammar_hits: str
    excerpt: str
    extraction_status: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conferences-root", type=Path, default=DEFAULT_CONFERENCES_ROOT)
    parser.add_argument("--output-csv", type=Path, default=DEFAULT_OUTPUT_CSV)
    parser.add_argument(
        "--path-filter",
        action="append",
        default=[],
        help="Case-insensitive substring filter applied to relative PDF paths. May be repeated.",
    )
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--limit", type=int, default=0, help="Optional limit after filtering. Zero means no limit.")
    parser.add_argument(
        "--min-score",
        type=int,
        default=0,
        help="If nonzero, only write rows where either score meets the threshold.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip PDFs already present in the output CSV.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_paths = list_pdf_paths(args.conferences_root, tuple(args.path_filter), args.limit)
    existing_rows = load_existing_rows(args.output_csv) if args.resume else {}
    pending_paths = [path for path in pdf_paths if str(path.relative_to(REPO_ROOT)) not in existing_rows]

    rows = list(existing_rows.values())
    if pending_paths:
        rows.extend(scan_paths(pending_paths, max_pages=args.max_pages, workers=args.workers))
    filtered_rows = [row for row in rows if max(row.optimization_score, row.grammar_score) >= args.min_score]
    write_csv(args.output_csv, filtered_rows)
    return 0


def list_pdf_paths(root: Path, path_filters: tuple[str, ...], limit: int) -> list[Path]:
    filters = tuple(item.lower() for item in path_filters if item.strip())
    paths = sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".pdf")
    if not filters:
        selected = paths
    else:
        selected = []
        for path in paths:
            relative_path = str(path.relative_to(REPO_ROOT)).lower()
            if any(item in relative_path for item in filters):
                selected.append(path)
    if limit > 0:
        return selected[:limit]
    return selected


def load_existing_rows(path: Path) -> dict[str, ScanResult]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            str(row["relative_path"]): ScanResult(
                relative_path=str(row["relative_path"]),
                venue=str(row["venue"]),
                title=str(row["title"]),
                optimization_score=int(row["optimization_score"]),
                grammar_score=int(row["grammar_score"]),
                optimization_hits=str(row["optimization_hits"]),
                grammar_hits=str(row["grammar_hits"]),
                excerpt=str(row["excerpt"]),
                extraction_status=str(row["extraction_status"]),
            )
            for row in reader
        }


def scan_paths(paths: list[Path], *, max_pages: int, workers: int) -> list[ScanResult]:
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        rows = list(executor.map(lambda path: scan_one_pdf(path, max_pages=max_pages), paths))
    rows.sort(key=lambda row: (-max(row.optimization_score, row.grammar_score), row.relative_path))
    return rows


def scan_one_pdf(path: Path, *, max_pages: int) -> ScanResult:
    relative_path = str(path.relative_to(REPO_ROOT))
    venue = path.relative_to(REPO_ROOT).parts[1]
    try:
        text = extract_text(path, max_pages=max_pages)
    except subprocess.CalledProcessError as exc:
        return ScanResult(
            relative_path=relative_path,
            venue=venue,
            title=path.stem,
            optimization_score=0,
            grammar_score=0,
            optimization_hits="",
            grammar_hits="",
            excerpt=str(exc.stderr or exc.stdout or "").strip()[:240],
            extraction_status="extract-error",
        )

    normalized = normalize_text(text)
    opt_score, opt_hits = score_text(normalized, OPTIMIZATION_PHRASES)
    grammar_score, grammar_hits = score_text(normalized, GRAMMAR_PHRASES)
    excerpt = select_excerpt(normalized)
    status = "ok" if normalized else "empty"
    return ScanResult(
        relative_path=relative_path,
        venue=venue,
        title=extract_title(text, fallback=path.stem),
        optimization_score=opt_score,
        grammar_score=grammar_score,
        optimization_hits=", ".join(hit for hit, _ in opt_hits[:8]),
        grammar_hits=", ".join(hit for hit, _ in grammar_hits[:8]),
        excerpt=excerpt,
        extraction_status=status,
    )


def extract_text(path: Path, *, max_pages: int) -> str:
    completed = subprocess.run(
        [
            "pdftotext",
            "-q",
            "-f",
            "1",
            "-l",
            str(max_pages),
            "-nopgbrk",
            str(path),
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def normalize_text(text: str) -> str:
    collapsed_lines = []
    for raw_line in text.replace("\x0c", "\n").splitlines():
        line = re.sub(r"\s+", " ", raw_line.strip())
        if line:
            collapsed_lines.append(line)
    return "\n".join(collapsed_lines)


def extract_title(text: str, *, fallback: str) -> str:
    lines = [re.sub(r"\s+", " ", line.strip()) for line in text.splitlines()]
    start_index = 0
    for index, line in enumerate(lines):
        if PAPER_MARKER_PATTERN.match(line):
            start_index = index + 1
            break
    candidates = [line for line in lines[start_index:] if is_title_candidate(line)]
    if not candidates:
        return fallback
    title_lines = [candidates[0]]
    for line in candidates[1:4]:
        if looks_like_author_line(line):
            break
        if len(" ".join(title_lines)) + len(line) > 180:
            break
        title_lines.append(line)
    return " ".join(title_lines)


def is_title_candidate(line: str) -> bool:
    if not line:
        return False
    lowered = line.lower()
    if any(lowered.startswith(prefix) for prefix in TITLE_SKIP_PREFIXES):
        return False
    if any(fragment in lowered for fragment in TITLE_SKIP_CONTAINS):
        return False
    if PAPER_MARKER_PATTERN.match(line):
        return False
    if lowered in {"abstract", "keywords", "nomenclature"}:
        return False
    if len(line) < 20:
        return False
    if re.fullmatch(r"[A-Z0-9 .,:;()/-]+", line):
        return True
    return bool(re.search(r"[A-Za-z]{4,}", line))


def looks_like_author_line(line: str) -> bool:
    if "university" in line.lower():
        return True
    if re.search(r"\b(and|department|school|laboratory)\b", line.lower()):
        return True
    comma_count = line.count(",")
    return comma_count >= 2 and len(line.split()) <= 18


def score_text(text: str, phrases: tuple[tuple[str, int], ...]) -> tuple[int, list[tuple[str, int]]]:
    lowered = text.lower()
    hits: list[tuple[str, int]] = []
    score = 0
    for phrase, weight in phrases:
        count = lowered.count(phrase)
        if count <= 0:
            continue
        capped_count = min(count, 3)
        score += weight * capped_count
        hits.append((phrase, weight))
    hits.sort(key=lambda item: (-item[1], item[0]))
    return score, hits


def select_excerpt(text: str) -> str:
    for line in text.splitlines():
        lowered = line.lower()
        if any(phrase in lowered for phrase, _ in OPTIMIZATION_PHRASES):
            return line[:240]
        if any(phrase in lowered for phrase, _ in GRAMMAR_PHRASES):
            return line[:240]
    return text.splitlines()[0][:240] if text else ""


def write_csv(path: Path, rows: list[ScanResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows.sort(key=lambda row: (-max(row.optimization_score, row.grammar_score), row.relative_path))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "relative_path",
                "venue",
                "title",
                "optimization_score",
                "grammar_score",
                "optimization_hits",
                "grammar_hits",
                "excerpt",
                "extraction_status",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "relative_path": row.relative_path,
                    "venue": row.venue,
                    "title": row.title,
                    "optimization_score": row.optimization_score,
                    "grammar_score": row.grammar_score,
                    "optimization_hits": row.optimization_hits,
                    "grammar_hits": row.grammar_hits,
                    "excerpt": row.excerpt,
                    "extraction_status": row.extraction_status,
                }
            )


if __name__ == "__main__":
    raise SystemExit(main())
