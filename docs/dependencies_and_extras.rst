Dependencies And Extras
=======================

Base install
------------

The base package installs only NumPy:

.. code-block:: bash

   pip install design-research-problems

Optimization baselines
----------------------

The representative optimization `solve()` baselines ship in the base install;
no extra dependency is required.

Grammar support
---------------

The grammar problem can evaluate states only when the optional `trussme`
dependency is installed:

.. code-block:: bash

   pip install design-research-problems[grammar]

In a local editable checkout of this repository, the convenience Make target
installs the same dependency:

.. code-block:: bash

   make install-trussme
