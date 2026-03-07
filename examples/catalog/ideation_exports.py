"""Render JSON and CSV exports for the ideation prompt index."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print compact JSON and CSV previews."""
    catalog = derp.get_ideation_catalog()
    json_payload = catalog.export_prompt_index(format="json")
    csv_payload = catalog.export_prompt_index(format="csv")
    print(json_payload.splitlines()[0])
    print(csv_payload.splitlines()[0])
    print(csv_payload.splitlines()[1])


if __name__ == "__main__":
    main()
