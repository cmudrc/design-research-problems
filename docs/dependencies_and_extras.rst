Dependencies And Extras
=======================

Base install
------------

The base package installs NumPy and SciPy:

.. code-block:: bash

   pip install design-research-problems

Optimization baselines
----------------------

The representative optimization `solve()` baselines use SciPy's constrained
optimizers and ship in the base install; no extra dependency is required.

Battery evaluation support
--------------------------

Battery grammar evaluation is optional and installs ``pybamm>=25.12,<26``.
The package uses PyBaMM only to extract a fixed-ambient, SOC-indexed single-cell
surrogate; the library still performs the pack-level circuit simulation. There
is no packaged fallback for battery evaluation when a supported PyBaMM install is
not available:

.. code-block:: bash

   pip install design-research-problems[battery]

Truss support
-------------

The planar and 3D truss grammar problems can evaluate states only when the
optional `trussme` dependency is installed. The packaged truss optimization
problems also require `trussme` because their objectives and constraints are
structural:

.. code-block:: bash

   pip install design-research-problems[grammar]

In a local editable checkout of this repository, the convenience Make target
installs the same dependency:

.. code-block:: bash

   make install-trussme

For the battery evaluator:

.. code-block:: bash

   make install-pybamm
