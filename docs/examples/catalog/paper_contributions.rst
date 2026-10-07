Paper Contributions
===================

Source: ``examples/catalog/paper_contributions.py``

Introduction
------------

Select a packaged ideation problem and carry its exact prompt lineage and curated
sources into the shared paper-contribution contract.

Technical Implementation
------------------------

1. Load writing support by stable problem ID.
2. Verify that every contribution citation resolves to an exported reference.
3. Print contribution and reporting-gap identifiers for downstream inspection.

.. literalinclude:: ../../../examples/catalog/paper_contributions.py
   :language: python
   :lines: 20-
   :linenos:

Expected Results
----------------

.. rubric:: Run Command

.. code-block:: bash

   PYTHONPATH=src python examples/catalog/paper_contributions.py

Prints contract version 0.1.0, three peanut-shelling references, Background and
Methods contributions, and a visible gap for the provisional source record.

References
----------

- docs/paper_contributions.rst
