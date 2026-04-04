Catalog Guide
=============

Use this page when you are still deciding *which* packaged problem to start
with. The generated catalog under :doc:`problem_catalog/index` is the complete
inventory; this guide is the curated entry point.

Role Labels Used In This Guide
------------------------------

- **Canonical benchmark**: the recommended representative benchmark for a family when you want a stable comparison target.
- **Example**: the lightest or clearest teaching entry point for learning the family API.
- **Convenience demo**: a useful integration showcase that is intentionally narrower than the family's deepest benchmark surface.

Family Start Table
------------------

.. list-table::
   :header-rows: 1

   * - Family
     - Recommended starting point
     - Canonical benchmark
     - Example or demo
   * - Text
     - Start with :doc:`problem_catalog/text/ideation_peanut_shelling` when you want a citation-backed ideation brief with several related variants nearby.
     - :doc:`problem_catalog/text/ideation_peanut_shelling`
     - :doc:`problem_catalog/text/ideation_accessible_drinking_fountain`
   * - Decision
     - Start with :doc:`problem_catalog/decision/decision_laptop_design_profit_maximization` for the clearest single-problem introduction to structured alternatives and evaluations.
     - :doc:`problem_catalog/decision/decision_laptop_design_profit_maximization`
     - :doc:`problem_catalog/decision/decision_mseval_safety_helmet_lightweight`
   * - Optimization
     - Start with :doc:`problem_catalog/optimization/pill_capsule_min_area` if you want the lightest local optimization loop before moving to larger benchmarks.
     - :doc:`problem_catalog/optimization/planar_truss_span_mass_min`
     - :doc:`problem_catalog/optimization/pill_capsule_min_area`
   * - Grammar
     - Start with :doc:`problem_catalog/grammar/planar_truss_span` for a representative sequential constructive benchmark with explicit state transitions.
     - :doc:`problem_catalog/grammar/planar_truss_span`
     - :doc:`problem_catalog/grammar/iot_home_cooling_system_design`
   * - MCP
     - Start with :doc:`problem_catalog/mcp/mcp_build123d_parametric_mounting_bracket`; it is both the family benchmark and the clearest integration demo today.
     - :doc:`problem_catalog/mcp/mcp_build123d_parametric_mounting_bracket`
     - :doc:`problem_catalog/mcp/mcp_build123d_parametric_mounting_bracket`

Recommended Use By Intent
-------------------------

.. list-table::
   :header-rows: 1

   * - Your goal
     - Start family
     - Why
   * - Benchmark open-ended ideation or prompt framing
     - Text
     - Text problems package the benchmark brief itself and keep the research prompt visible.
   * - Compare explicit alternatives against criteria
     - Decision
     - Decision problems expose candidate spaces and reusable evaluation helpers directly.
   * - Measure algorithmic performance under objectives and constraints
     - Optimization
     - Optimization problems expose typed bounds and packaged baseline solve routines.
   * - Study constructive action sequences and transition structure
     - Grammar
     - Grammar problems make the state/action model explicit for trace-oriented analysis.
   * - Exercise an external tool runtime through a packaged problem shell
     - MCP
     - MCP problems wrap upstream tool servers as a first-class family.

What To Read Next
-----------------

- Use :doc:`problems/index` for the conceptual family overview.
- Use :doc:`problem_catalog/index` for the full generated inventory once you know the family.
- Use :doc:`downstream_metadata_contract` when you want to carry packaged-problem metadata into experiments or analysis.
