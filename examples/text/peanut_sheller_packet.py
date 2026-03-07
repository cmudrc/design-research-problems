"""Render the text prompt packet for the Fu et al. peanut shelling problem."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Render and print the full prompt packet for the text problem."""
    problem = derp.get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    print(problem.render_brief())


if __name__ == "__main__":
    main()
