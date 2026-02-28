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

Local TrussMe support
---------------------

The grammar problem can evaluate states without the local `TrussMe` checkout
only when a fake adapter is supplied in tests. Real evaluation requires the
local checkout and editable install:

.. code-block:: bash

   make install-trussme-local
