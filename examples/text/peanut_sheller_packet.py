"""Render the text prompt packet for the peanut sheller problem."""

from __future__ import annotations

from design_research_problems import get_problem


def main() -> None:
    """Render and print the full prompt packet for the text problem."""
    problem = get_problem("peanut_sheller_fu2010")
    print(problem.render_packet())


if __name__ == "__main__":
    main()
