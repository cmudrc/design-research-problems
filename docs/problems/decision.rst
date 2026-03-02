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

Example
-------

.. code-block:: python

   from itertools import islice

   from design_research_problems import get_problem

   problem = get_problem("decision_laptop_design_profit_maximization")

   variable_specs = problem.decision_variable_specs
   objective_specs = problem.objective_specs
   constraint_specs = problem.constraint_specs
   option_count = problem.option_count

   first_three_options = list(islice(problem.iter_options(), 3))
   best = problem.best_option()

   print(variable_specs[0].symbol, variable_specs[0].lower_bound, variable_specs[0].upper_bound)
   print(objective_specs[0].label, objective_specs[0].executable)
   print(constraint_specs[0].key, constraint_specs[0].expression)
   print(option_count)
   print(first_three_options[0].values)
   print(best.predicted_share)

The discrete evaluator scores the 3,125 explicit Table 5 conjoint profiles
against the ten Table 6 competitor profiles using the Table 8 part-worth logit
model. The five engineering constraints are exposed as typed formulas for
inspection and downstream tooling, but they are not numerically enforced by the
discrete evaluator in this version.
