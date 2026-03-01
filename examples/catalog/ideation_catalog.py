"""Inspect the packaged ideation catalog."""

from __future__ import annotations

from design_research_problems import get_ideation_catalog


def main() -> None:
    """Print a small ideation catalog summary."""
    catalog = get_ideation_catalog()
    print("prompts", len(catalog.list_prompts()))
    print("variants", len(catalog.list_variants()))
    print("families", len(catalog.list_families()))
    print("studies", len(catalog.list_studies()))
    for prompt in catalog.list_prompts()[:3]:
        print(prompt.prompt_id, prompt.family_id, prompt.status)


if __name__ == "__main__":
    main()
