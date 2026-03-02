"""Render JSON and CSV exports for the ideation prompt index."""

from __future__ import annotations

from design_research_problems import get_ideation_catalog


def main() -> None:
    """Print compact JSON and CSV previews."""
    catalog = get_ideation_catalog()
    json_payload = catalog.export_prompt_index(format="json")
    csv_payload = catalog.export_prompt_index(format="csv")
    print(json_payload.splitlines()[0])
    print(csv_payload.splitlines()[0])
    print(csv_payload.splitlines()[1])


if __name__ == "__main__":
    main()
