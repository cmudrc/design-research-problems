# AGENTS.md

## Purpose

This repository is a Python 3.12+ compendium of design research problems across
text, decision, optimization, grammar-based, and MCP-facing workflows. Keep
changes focused, preserve deterministic behavior in packaged problem
evaluations, and prefer reusable catalog-backed implementations over one-off ad
hoc assets.

## Setup

- Create and activate a virtual environment:
  - `python -m venv .venv`
  - `source .venv/bin/activate`
- The preferred interpreter target lives in `.python-version` (`3.12`).
- Install local tooling with `make dev`.
- Use `PYTHONPATH=src` when running scripts or examples directly.

## Testing And Validation

Use the smallest useful check while iterating, then run the full gate before
merging.

- Fast local loop:
  - `make fmt`
  - `make lint`
  - `make type`
  - `make test`
- If examples changed:
  - `make examples-smoke`
  - `make examples-test`
- If docs or generated catalog docs changed:
  - `make docs-check`
  - `make docs-build`
- If coverage-sensitive behavior changed:
  - `make coverage`
- Pre-merge baseline:
  - `make ci`
- Pre-publish baseline:
  - `make release-check`

## Public Vs Private Boundaries

- The supported public surface is the curated export list in
  `src/design_research_problems/__init__.py`.
- Family facade modules under `src/design_research_problems/problems/` are the
  preferred public entry points for shared contracts and packaged
  implementations.
- Underscored modules are internal and may change without notice; avoid growing
  user-facing examples/docs around them unless there is no stable public
  alternative.
- If a public export changes, update the coupled API/docs/tests in the same
  change.

## Behavioral Guardrails

- Keep packaged problem evaluations deterministic and offline by default.
- Update tests, examples, docs, and catalog assets together when behavior or
  public packaging changes.
- Prefer extending existing scripts under `scripts/` before writing one-off
  extraction or generation logic.
- For conference-paper mining, prefer `scripts/audit_conference_papers.py` and
  write long-running notes under `artifacts/`, not `docs/`.
- Prefer paper-backed formulations over guessed reconstructions; if a paper is
  insufficiently specified, log it as such instead of silently filling gaps.
- Keep the base install lean and avoid introducing optional-dependency behavior
  into default test paths.

## Release Naming

- Theme: endangered species.
- Monthly work-cycle names are shared across milestone titles, release PR
  titles, and release branches.
- Name the cycle for the month the work is done, not the later drop month.
  - Milestone title / PR title: `{base name} - {Work month YYYY}`
  - Release branch: slugified full title, for example
    `monarch-maze-april-2026`
- Milestone due dates should land in the first week of the following month.
- Milestone descriptions must use:
  - `Work month: {Month YYYY}.`
  - `Theme source: <url>`
- Release PR bodies must repeat the same `Theme source:` link used on the
  milestone and refer to the same work month named in the title.
- Never reuse an exact base name or the same primary subject across any work
  month or any of the four design-research module repos unless all four
  `AGENTS.md` files are intentionally updated together.
- Before adding a new release name, check the `Release Naming` tables in all
  four repos to avoid repeats.

| Work month | Target drop | Base name | Source subject |
| --- | --- | --- | --- |
| March 2026 | April 1, 2026 | Axolotl Array | Axolotl |
| April 2026 | May 1, 2026 | Monarch Maze | Monarch butterfly |
| May 2026 | June 1, 2026 | Jaguar Junction | Jaguar |
| June 2026 | July 1, 2026 | Saola Sandbox | Saola |
| July 2026 | August 1, 2026 | Orangutan Obstacle | Orangutan |
| August 2026 | September 1, 2026 | Numbat Nexus | Numbat |
| September 2026 | October 1, 2026 | Dhole Dilemma | Dhole |
| October 2026 | November 1, 2026 | Kakapo Knot | Kakapo |
| November 2026 | December 1, 2026 | Vaquita Vault | Vaquita |
| December 2026 | January 1, 2027 | Pangolin Puzzle | Pangolin |
## Keep This File Up To Date

Update this file whenever contributor workflow changes, especially when setup
commands, validation commands, audit scripts, or public API expectations
change.
