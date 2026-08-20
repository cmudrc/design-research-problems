Typical Workflow
================

1. Choose inputs
----------------

Browse the catalog and choose problem IDs aligned with the research question.

2. Instantiate core objects
---------------------------

Load problem instances and inspect constraints, state representation, prompt
content, and available evaluator interfaces.

3. Execute or inspect
---------------------

Generate candidate solutions, enumerate transitions, or call evaluators.

4. Capture artifacts
--------------------

Record solution state, metrics, and any domain-specific outputs needed for
comparison or reporting.

5. Compose the ecosystem seams
------------------------------

Let `design-research-experiments
<https://cmudrc.github.io/design-research-experiments/>`_ resolve the packaged
problem through ``design_research_problems.integration``, invoke participants
from `design-research-agents
<https://cmudrc.github.io/design-research-agents/>`_, and preserve the problem
metadata for `design-research-analysis
<https://cmudrc.github.io/design-research-analysis/>`_. The experiments layer
owns cross-package orchestration; this package owns problem resolution and
evaluation.

Dependency Caveats
------------------

The base install supports text and decision problems, generic grammar
transitions, and analytic-surrogate battery paths. Install ``grammar`` for
``trussme``-backed planar or 3D truss structural evaluation, ``battery`` for
PyBaMM-backed battery-fidelity modes, and the relevant ``mcp`` or ``cad`` extra
for external-tool workflows. Plan installation profiles per study protocol
rather than installing every extra by default.
