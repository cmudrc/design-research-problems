Dependencies And Extras
=======================

Base install
------------

The base package installs only NumPy:

.. code-block:: bash

   pip install design-research-problems

Optimization support
--------------------

SciPy-backed solving is optional:

.. code-block:: bash

   pip install design-research-problems[opt]

Battery evaluation support
--------------------------

Battery grammar evaluation is optional and installs ``pybamm>=25.12,<26``.
The package uses PyBaMM only to extract a fixed-ambient, SOC-indexed single-cell
surrogate; the library still performs the pack-level circuit simulation. There
is no packaged fallback for battery evaluation when a supported PyBaMM install is
not available:

.. code-block:: bash

   pip install design-research-problems[battery]

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

For the battery evaluator:

.. code-block:: bash

   make install-pybamm
