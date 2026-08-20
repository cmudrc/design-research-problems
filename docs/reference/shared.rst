Shared Types
============

Exceptions
----------

.. autoexception:: design_research_problems.MissingOptionalDependencyError

.. autoexception:: design_research_problems.ProblemEvaluationError

Metadata
--------

For the downstream compatibility-guaranteed subset used by study-generation
tooling, see :doc:`../downstream_metadata_contract`.

The private ``problems._metadata`` implementation path is contributor-only.
Public users should import these compatibility-guaranteed aliases from the
top-level package.

.. autoclass:: design_research_problems.ProblemKind
   :members:
   :no-index:

.. autoclass:: design_research_problems.ProblemMetadata
   :members:
   :no-index:

.. autoclass:: design_research_problems.ProblemCatalogSummary
   :members:
   :no-index:

.. autoclass:: design_research_problems.ProblemTaxonomy
   :members:
   :no-index:

.. autoclass:: design_research_problems.Citation
   :members:
   :no-index:

.. autoclass:: design_research_problems.ProblemAsset
   :members:
   :no-index:
