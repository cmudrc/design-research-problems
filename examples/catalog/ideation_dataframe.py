"""Render pandas DataFrames for the ideation catalog when pandas is installed."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print one short DataFrame preview or an install hint."""
    catalog = derp.get_ideation_catalog()
    try:
        dataframe = catalog.prompts_dataframe()
    except derp.MissingOptionalDependencyError as exc:
        print(str(exc))
        return
    print(tuple(dataframe.columns))
    print(len(dataframe))


if __name__ == "__main__":
    main()
