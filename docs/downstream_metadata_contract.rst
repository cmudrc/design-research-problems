Downstream Metadata Contract
============================

Use this page when you are consuming ``design-research-problems`` from
``design-research-experiments``, the umbrella package, or your own study
generation tooling.

Stable Fields
-------------

The initial downstream compatibility contract is intentionally narrow. These
fields on :class:`design_research_problems.ProblemMetadata` are the ones
downstream study-generation code may rely on:

- ``problem_id``: Stable catalog identifier.
- ``title``: User-facing display title.
- ``summary``: Short one-paragraph problem description.
- ``kind``: High-level family label from :class:`design_research_problems.ProblemKind`.
- ``capabilities``: Controlled-vocabulary implementation and packaging flags.
- ``study_suitability``: Controlled-vocabulary study-use flags.
- ``feature_flags``: Sorted union of ``capabilities`` and ``study_suitability``.
- ``implementation``: Optional ``module:attribute`` import path when a public executable binding exists.

Initial Use Cases
-----------------

This contract is the supported metadata surface for:

- Choosing benchmark slices by family or feature flags.
- Building study/problem registries in ``design-research-experiments``.
- Exposing problem summaries and titles in umbrella examples and reports.
- Selecting control-condition and intervention-ready task subsets.

Controlled Vocabularies
-----------------------

``capabilities`` values come from ``KNOWN_PROBLEM_CAPABILITIES``:

- ``statement-markdown``
- ``citation-backed``
- ``prompt-packet``
- ``packaged-assets``
- ``bounded-variables``
- ``equality-constraint``
- ``baseline-solver``
- ``discrete-actions``
- ``optional-evaluator``
- ``external-adapter``
- ``serializable-state``

``study_suitability`` values come from ``KNOWN_STUDY_SUITABILITY``:

- ``human-subjects-ready``
- ``ideation-friendly``
- ``requirements-study-ready``
- ``variety-study-ready``
- ``intervention-ready``

Fallback Behavior
-----------------

- ``feature_flags`` is always derived from the two controlled-vocabulary fields.
- ``implementation`` may be ``None``; downstream consumers must treat that as
  "no public executable import path promised."
- Fields outside this page, such as detailed taxonomy internals, citations,
  and assets, remain useful but are not yet part of the downstream generation
  compatibility promise.

Where To Read It
----------------

- ``ProblemRegistry.list()`` for catalog-level metadata.
- ``get_problem(problem_id).metadata`` for one resolved packaged problem.
- :doc:`reference/shared` for the full typed metadata API.
