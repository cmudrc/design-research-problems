"""Render pandas DataFrames for the ideation catalog when pandas is installed."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_ideation_catalog


def main() -> None:
    """Print one short DataFrame preview or an install hint."""
    catalog = get_ideation_catalog()
    try:
        dataframe = catalog.prompts_dataframe()
    except MissingOptionalDependencyError as exc:
        print(str(exc))
        return
    print(tuple(dataframe.columns))
    print(len(dataframe))


if __name__ == "__main__":
    main()
