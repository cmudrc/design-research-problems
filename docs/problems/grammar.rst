Grammar Problems
================

Grammar problems describe discrete design actions over a library-owned state.

The seed entry is `planar_truss_span`, which translates a serializable planar
topology state into a fresh `trussme.Truss` for evaluation.

`TrussMe` is a local developer dependency in this repo:

- It is not required for the base install.
- It is not installed in default CI.
- It is required only for real grammar evaluation.
