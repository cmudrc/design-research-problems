# Planar truss span grammar problem

Create a stable, lightweight planar truss spanning a fixed distance between a
left pinned support and a right roller support. The grammar begins with the
supports and one loaded free joint. Designers can add interior joints, add
members, and remove members.

States are evaluated by translating the library-owned grammar state into a
fresh `trussme.Truss`, applying the load, and attempting a structural
analysis. Singular or unstable states are treated as infeasible results.
