Grammar Problems
================

Grammar problems describe discrete design actions over a library-owned state.

The seed entry is `planar_truss_span`, which translates a serializable planar
topology state into a fresh `trussme.Truss` for evaluation. The catalog also
includes six `planar_roof_truss_*` variants that approximate the planar roof
truss formulations discussed by Shea and Cagan, including multi-load and
symmetry-constrained cases.

`trussme` is an optional dependency:

- It is not required for the base install.
- It is available as the `grammar` extra.
- It is not installed in default CI.
- It is required only for real grammar evaluation.
