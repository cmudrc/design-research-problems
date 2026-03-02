"""Generate packaged MSEval decision problems and empirical benchmark assets."""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import statistics
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG_ROOT = REPO_ROOT / "src" / "design_research_problems" / "_assets" / "catalog"

MATERIALS = (
    "Steel",
    "Aluminium",
    "Titanium",
    "Glass",
    "Wood",
    "Thermoplastic",
    "Elastomer",
    "Thermoset",
    "Composite",
)

MSEVAL_BIBTEX = """@misc{jain2024msevaldatasetmaterialselection,
      title={MSEval: A Dataset for Material Selection in Conceptual Design to Evaluate Algorithmic Models},
      author={Yash Patawari Jain and Daniele Grandi and Allin Groom and Brandon Cramer and Christopher McComb},
      year={2024},
      eprint={2407.09719},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/2407.09719},
}
"""


@dataclass(frozen=True)
class PromptDefinition:
    """One design-plus-criterion prompt definition from MSEval."""

    question: str
    """Stable source question key such as ``Q1``."""
    design: str
    """Human-readable design brief label."""
    criterion: str
    """Human-readable criterion label."""

    @property
    def design_slug(self) -> str:
        """Return the normalized design slug.

        Returns:
            Lowercase underscore slug for the design label.
        """
        return slugify(self.design)

    @property
    def criterion_slug(self) -> str:
        """Return the normalized criterion slug.

        Returns:
            Lowercase underscore slug for the criterion label.
        """
        return slugify(self.criterion)

    @property
    def dir_slug(self) -> str:
        """Return the catalog directory slug.

        Returns:
            Stable directory slug for the packaged prompt.
        """
        return f"mseval_{self.design_slug}_{self.criterion_slug}"

    @property
    def problem_id(self) -> str:
        """Return the packaged problem identifier.

        Returns:
            Stable package-facing problem identifier.
        """
        return f"decision_{self.dir_slug}"

    @property
    def title(self) -> str:
        """Return the human-readable packaged title.

        Returns:
            Display title used in the packaged manifest.
        """
        return f"Decision Problem - MSEval {self.design} ({self.criterion})"


@dataclass(frozen=True)
class ChoiceStats:
    """Aggregated metrics for one material choice."""

    key: str
    """Canonical lowercase material key."""
    label: str
    """Human-readable material label."""
    top_choice_share: float
    """Tie-adjusted share of top-rated expert responses."""
    mean_rating: float
    """Mean expert rating on the 0-10 scale."""
    median_rating: float
    """Median expert rating on the 0-10 scale."""
    std_rating: float
    """Sample standard deviation of the expert ratings."""


@dataclass(frozen=True)
class PromptStats:
    """Aggregated benchmark metrics for one prompt."""

    response_count: int
    """Number of complete valid responses for the prompt."""
    choices: tuple[ChoiceStats, ...]
    """Per-material aggregates in canonical source order."""


def slugify(text: str) -> str:
    """Return a deterministic lowercase underscore slug.

    Args:
        text: Human-readable source text.

    Returns:
        Normalized ASCII slug.
    """
    normalized = text.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the generator.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(description="Generate packaged MSEval decision problems.")
    parser.add_argument("--key-questions-csv", required=True, type=Path)
    parser.add_argument("--clean-responses-csv", required=True, type=Path)
    parser.add_argument("--catalog-root", type=Path, default=DEFAULT_CATALOG_ROOT)
    return parser.parse_args()


def load_prompts(path: Path) -> tuple[PromptDefinition, ...]:
    """Load the ordered prompt definitions from ``key_questions.csv``.

    Args:
        path: CSV file path.

    Returns:
        Parsed prompt definitions in file order.

    Raises:
        ValueError: If the CSV does not contain the expected 16 prompts.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        prompts = tuple(
            PromptDefinition(
                question=str(row["Question"]).strip(),
                design=str(row["Design"]).strip(),
                criterion=str(row["Criterion"]).strip(),
            )
            for row in reader
        )
    if len(prompts) != 16:
        raise ValueError(f"Expected 16 prompts in {path}, found {len(prompts)}.")
    return prompts


def load_response_rows(path: Path) -> tuple[dict[str, str], ...]:
    """Load the raw response rows from ``clean_responses.csv``.

    Args:
        path: CSV file path.

    Returns:
        CSV rows as string-keyed mappings.
    """
    with path.open(newline="", encoding="utf-8") as handle:
        return tuple(dict(row) for row in csv.DictReader(handle))


def compute_prompt_stats(
    prompts: tuple[PromptDefinition, ...],
    rows: tuple[dict[str, str], ...],
) -> dict[str, PromptStats]:
    """Compute per-prompt empirical material aggregates.

    Args:
        prompts: Ordered prompt definitions.
        rows: Raw cleaned response rows.

    Returns:
        Mapping of packaged problem IDs to aggregated prompt statistics.

    Raises:
        ValueError: If any prompt yields no complete valid responses.
    """
    output: dict[str, PromptStats] = {}
    for prompt in prompts:
        material_values = {material: [] for material in MATERIALS}
        top_choice_credit = {material: 0.0 for material in MATERIALS}
        response_count = 0

        for row in rows:
            parsed_values: dict[str, float] = {}
            is_valid_row = True
            for material in MATERIALS:
                column = f"{prompt.question}_{material}"
                raw_value = row.get(column, "").strip()
                if not raw_value:
                    is_valid_row = False
                    break
                try:
                    parsed_values[material] = float(raw_value)
                except ValueError:
                    is_valid_row = False
                    break
            if not is_valid_row:
                continue

            response_count += 1
            max_score = max(parsed_values.values())
            top_materials = tuple(material for material in MATERIALS if parsed_values[material] == max_score)
            credit = 1.0 / len(top_materials)
            for material in MATERIALS:
                value = parsed_values[material]
                material_values[material].append(value)
                if material in top_materials:
                    top_choice_credit[material] += credit

        if response_count <= 0:
            raise ValueError(f"Prompt {prompt.question} produced no valid responses.")

        choices = tuple(
            ChoiceStats(
                key=slugify(material),
                label=material,
                top_choice_share=top_choice_credit[material] / response_count,
                mean_rating=statistics.fmean(material_values[material]),
                median_rating=float(statistics.median(material_values[material])),
                std_rating=statistics.stdev(material_values[material]) if len(material_values[material]) > 1 else 0.0,
            )
            for material in MATERIALS
        )
        output[prompt.problem_id] = PromptStats(response_count=response_count, choices=choices)
    return output


def rebuild_catalog_subtree(
    catalog_root: Path,
    prompts: tuple[PromptDefinition, ...],
    stats_by_problem: dict[str, PromptStats],
) -> None:
    """Replace the generated MSEval catalog subtree.

    Args:
        catalog_root: Root packaged catalog directory.
        prompts: Ordered prompt definitions.
        stats_by_problem: Precomputed aggregates keyed by problem ID.

    Raises:
        FileNotFoundError: If the catalog root does not exist.
    """
    if not catalog_root.exists():
        raise FileNotFoundError(f"Catalog root does not exist: {catalog_root}")
    target_root = catalog_root / "decision" / "material_selection"
    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    for prompt in prompts:
        destination = target_root / prompt.dir_slug
        destination.mkdir(parents=True, exist_ok=False)
        prompt_stats = stats_by_problem[prompt.problem_id]
        (destination / "problem.toml").write_text(render_problem_toml(prompt, prompt_stats), encoding="utf-8")
        (destination / "benchmark.toml").write_text(render_benchmark_toml(prompt_stats), encoding="utf-8")


def render_problem_toml(prompt: PromptDefinition, prompt_stats: PromptStats) -> str:
    """Render one minimal Python-backed problem manifest.

    Args:
        prompt: Prompt definition to render.
        prompt_stats: Aggregate statistics for the prompt.

    Returns:
        TOML manifest text.
    """
    statement = render_statement(prompt)
    lines = [
        f'problem_id = "{prompt.problem_id}"',
        f'title = "{prompt.title}"',
        (
            'summary = "Choose one material for '
            f"{prompt.design} with emphasis on {prompt.criterion}, using expert MSEval survey responses as the "
            'evaluation benchmark."'
        ),
        'kind = "decision"',
        ('implementation = "design_research_problems.problems.decision._mseval:MSEvalEmpiricalChoiceProblem"'),
        "statement = '''",
        statement,
        "'''",
        'capabilities = ["statement-markdown", "citation-backed"]',
        "study_suitability = []",
        "",
        "[taxonomy]",
        'formulation = "empirical_discrete_choice"',
        'design_variable_type = "categorical"',
        "is_dynamic = false",
        'orientation = "engineering_practical"',
        'objective_mode = "single"',
        'constraint_nature = "preference-derived"',
        (f'tags = ["decision", "material-selection", "mseval", "{prompt.design_slug}", "{prompt.criterion_slug}"]'),
        "",
        "[[citations]]",
        'key = "jain2024msevaldatasetmaterialselection"',
        'kind = "bibtex"',
        ('authors = ["Yash Patawari Jain", "Daniele Grandi", "Allin Groom", "Brandon Cramer", "Christopher McComb"]'),
        'title = "MSEval: A Dataset for Material Selection in Conceptual Design to Evaluate Algorithmic Models"',
        "year = 2024",
        'url = "https://arxiv.org/abs/2407.09719"',
        "raw_text = '''",
        MSEVAL_BIBTEX.strip(),
        "'''",
        "",
        "[parameters]",
        (f'decision_maker = "A designer selecting one material conceptually for a {prompt.design.lower()}."'),
        (
            'decision_scope = "Choose a single candidate material from the provided materials using an empirical '
            'preference benchmark derived from MSEval survey responses."'
        ),
        'default_choice_metric = "top-choice-share"',
        'benchmark_file = "benchmark.toml"',
        (
            'market_segment = "MSEval expert benchmark with '
            f'{prompt_stats.response_count} complete responses for this prompt."'
        ),
        "",
    ]
    return "\n".join(lines)


def render_benchmark_toml(prompt_stats: PromptStats) -> str:
    """Render one empirical benchmark payload.

    Args:
        prompt_stats: Aggregate statistics for the prompt.

    Returns:
        TOML benchmark text consumed by the Python implementation.
    """
    lines = [f"response_count = {prompt_stats.response_count}"]
    for choice in prompt_stats.choices:
        lines.extend(
            [
                "",
                "[[choices]]",
                f'key = "{choice.key}"',
                f'label = "{choice.label}"',
                f"top_choice_share = {format_float(choice.top_choice_share)}",
                f"mean_rating = {format_float(choice.mean_rating)}",
                f"median_rating = {format_float(choice.median_rating)}",
                f"std_rating = {format_float(choice.std_rating)}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def render_statement(prompt: PromptDefinition) -> str:
    """Render the human-readable Markdown statement for one prompt.

    Args:
        prompt: Prompt definition to render.

    Returns:
        Markdown statement text.
    """
    options = "\n".join(f"- {material}" for material in MATERIALS)
    return (
        f"# {prompt.title}\n\n"
        f"You are selecting a material for **{prompt.design}**.\n\n"
        f"Primary criterion: **{prompt.criterion}**.\n\n"
        "## Task\n"
        "1. Choose **one** material from the list below.\n"
        "2. Briefly justify the choice in terms of the stated criterion and likely use context.\n"
        "3. Optionally note one follow-up risk or tradeoff to validate next.\n\n"
        "## Candidate Materials\n"
        f"{options}\n\n"
        "## Output Format\n"
        "- Selected material:\n"
        "- Justification (3-6 sentences):\n"
        "- Risk or tradeoff to check next (optional):\n"
    )


def format_float(value: float) -> str:
    """Render one float in stable compact TOML form.

    Args:
        value: Numeric value to format.

    Returns:
        Compact decimal text with at least one decimal place.
    """
    formatted = f"{value:.6f}".rstrip("0").rstrip(".")
    if "." not in formatted:
        formatted = f"{formatted}.0"
    return formatted


def main() -> None:
    """Run the CLI entrypoint."""
    args = parse_args()
    prompts = load_prompts(args.key_questions_csv)
    rows = load_response_rows(args.clean_responses_csv)
    stats_by_problem = compute_prompt_stats(prompts, rows)
    rebuild_catalog_subtree(args.catalog_root, prompts, stats_by_problem)
    print(
        "Wrote "
        f"{len(prompts)} MSEval decision problems to "
        f"{(args.catalog_root / 'decision' / 'material_selection').resolve()}"
    )


if __name__ == "__main__":
    main()
