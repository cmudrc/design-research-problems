Quickstart
==========

This example shows the shortest meaningful path through
``design-research-problems``.

1. Install
----------

.. code-block:: bash

   pip install design-research-problems

Or install from source:

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -e .

2. Minimal Runnable Example
---------------------------

.. code-block:: python

   import design_research_problems as derp

   print(f"Catalog size: {len(derp.list_problems())}")
   problem = derp.get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
   print(problem.render_brief(include_citation=False))

3. What Happened
----------------

You loaded one packaged study task from the catalog and rendered its design
brief. This is the core pattern for building comparable task inputs before
adding evaluators, solvers, or orchestration.

4. Where To Go Next
-------------------

- :doc:`concepts`
- :doc:`typical_workflow`
- :doc:`problems/index`
- :doc:`examples/index`

Ecosystem Note
--------------

In a typical study, ``design-research-agents`` provides executable
participants, ``design-research-problems`` supplies the task,
``design-research-experiments`` defines the study structure, and
``design-research-analysis`` interprets the resulting records.
