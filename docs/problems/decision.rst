Decision Problems
=================

Decision problems package a reusable narrative statement plus a structured
decision frame: decision maker, scope, variables, objective, constraints, and
assumptions extracted from a source.

See :doc:`../problem_catalog/decision` for the generated per-problem catalog pages.

The initial entry is `decision_laptop_design_profit_maximization`, distilled
from Shiau, Tseng, Heutchy, and Michalek (2007) into a reusable decision-based
design brief for laptop configuration and pricing.

In addition to the narrative brief, each entry exposes typed structure plus one
shared candidate workflow:

- ``iter_candidates()``
- ``iter_evaluations()``
- ``rank_evaluations()``
- ``best_evaluation()``

The active mode is visible through ``candidate_kind``:

- ``"discrete-option"`` for explicit conjoint option spaces
- ``"empirical-choice"`` for benchmark-backed categorical choices

Examples
--------

Runnable scripts:

- ``examples/decision/laptop_design.py``
- ``examples/decision/mseval_material_choice.py``

Laptop design
~~~~~~~~~~~~~

.. code-block:: python

   from design_research_problems import get_problem

   problem = get_problem("decision_laptop_design_profit_maximization")

   top_three = problem.rank_evaluations()[:3]
   best = problem.best_evaluation()

   print(problem.metadata.problem_id)
   print(problem.objective_specs[0].key)
   print(problem.candidate_kind)
   print(problem.candidate_count)
   print(round(best.objective_value, 6), best.candidate_label)

MSEval empirical choice
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from design_research_problems import get_problem

   problem = get_problem("decision_mseval_safety_helmet_lightweight")

   top_three = problem.rank_evaluations()[:3]
   best = problem.best_evaluation()

   print(problem.metadata.problem_id)
   print(problem.objective_specs[0].key)
   print(problem.candidate_kind)
   print(problem.candidate_count)
   print(best.candidate_label, best.objective_value)
   print([entry.candidate_label for entry in top_three])

The discrete evaluator scores the 3,125 explicit Table 5 conjoint profiles
against the ten Table 6 competitor profiles using the Table 8 part-worth logit
model. The five engineering constraints are exposed as typed formulas for
inspection and downstream tooling, but they are not numerically enforced by the
discrete evaluator in this version.
