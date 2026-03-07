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

5. Connect to the next library
------------------------------

Pass problem references to ``design-research-agents`` for execution and to
``design-research-experiments`` for controlled study orchestration.

Dependency Caveats
------------------

Some families are lightweight (for example text and decision), while others
require optional extras (for example grammar, battery, or CAD/MCP workflows).
Plan installation profiles per study protocol rather than installing every extra
by default.
