Decision Problems
=================

Decision problems package a reusable narrative statement plus a structured
decision frame: decision maker, scope, variables, objective, constraints, and
assumptions extracted from a source.

The initial entry is `decision_laptop_design_profit_maximization`, distilled
from Shiau, Tseng, Heutchy, and Michalek (2007) into a reusable decision-based
design brief for laptop configuration and pricing.

In addition to the narrative brief, the laptop entry now exposes typed design
variables, discrete conjoint factors, competitor profiles, objective metadata,
constraint equations, and a discrete part-worth evaluator over the full
Cartesian option space.

Examples
--------

Runnable scripts:

- ``examples/decision/laptop_design.py``
- ``examples/decision/mseval_material_choice.py``

Laptop design
~~~~~~~~~~~~~

.. code-block:: python

   from heapq import nlargest

   from design_research_problems import get_problem

   problem = get_problem("decision_laptop_design_profit_maximization")

   top_three = nlargest(3, problem.iter_option_evaluations(), key=lambda evaluation: evaluation.objective_value)
   best = top_three[0]

   print(problem.metadata.problem_id)
   print(problem.objective_specs[0].key)
   print(problem.option_count)
   print(round(best.objective_value, 6), dict(best.option.values))

MSEval empirical choice
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from design_research_problems import get_problem

   problem = get_problem("decision_mseval_safety_helmet_lightweight")

   top_three = problem.rank_choices()[:3]
   best = top_three[0]

   print(problem.metadata.problem_id)
   print(problem.objective_specs[0].key)
   print(len(problem.choice_options))
   print(best.choice_label, best.objective_value)
   print([entry.choice_label for entry in top_three])

The discrete evaluator scores the 3,125 explicit Table 5 conjoint profiles
against the ten Table 6 competitor profiles using the Table 8 part-worth logit
model. The five engineering constraints are exposed as typed formulas for
inspection and downstream tooling, but they are not numerically enforced by the
discrete evaluator in this version.
