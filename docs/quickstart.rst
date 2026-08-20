Quickstart
==========

This example shows the shortest meaningful path through
``design-research-problems``.

Requires Python 3.12+.

.. note::

   For an editor-first setup, interpreter selection, and debugging flow, see
   :doc:`vscode_start`.

1. Install
----------

.. code-block:: bash

   python -m pip install design-research-problems

On Windows, if ``python`` resolves to an older interpreter, use
``py -3.12 -m pip install design-research-problems`` and
``py -3.12 -m venv .venv``.

Or install from source:

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .

2. Minimal Runnable Example
---------------------------

.. code-block:: python

   import design_research_problems as derp

   print(f"Catalog size: {len(derp.list_problems())}")
   summaries = derp.search_problem_summaries(text="pill", kind="optimization")
   print(summaries[0].to_dict())

   problem = derp.get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
   print(problem.render_brief(include_citation=False))

   optimization = derp.get_problem("pill_capsule_min_area")
   if isinstance(optimization, derp.OptimizationProblem):
       print(optimization.solver_hints())

3. What Happened
----------------

You loaded one packaged study task from the catalog and rendered its design
brief. This is the core pattern for building comparable task inputs before
adding evaluators, solvers, or orchestration.

``search_problem_summaries`` returns compact metadata for selection and routing
without putting every full problem brief into an agent context window.
Optimization problems also expose ``solver_hints()`` so callers can see bounds,
variable domain, constraint counts, and a solver-family hint directly.

4. Where To Go Next
-------------------

- :doc:`concepts`
- :doc:`typical_workflow`
- :doc:`problems/index`
- :doc:`examples/index`
- :doc:`api`

Ecosystem Note
--------------

In a typical study, `design-research-agents
<https://cmudrc.github.io/design-research-agents/>`_ provides executable
participants, ``design-research-problems`` supplies the task,
`design-research-experiments
<https://cmudrc.github.io/design-research-experiments/>`_ defines and
orchestrates the study, and `design-research-analysis
<https://cmudrc.github.io/design-research-analysis/>`_ interprets the resulting
records.
