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
- Monthly release names are shared across milestone titles, release PR titles,
  and release branches.
  - Milestone title / PR title: `{base name} - {Month YYYY}`
  - Release branch: slugified full title, for example
    `monarch-maze-may-2026`
- Milestone descriptions must use:
  - `Tracks {previous month YYYY} work.`
  - `Theme source: <url>`
- Release PR bodies must repeat the same `Theme source:` link used on the
  milestone.
- Never reuse an exact base name or the same primary subject across any month
  or any of the four design-research module repos unless all four `AGENTS.md`
  files are intentionally updated together.
- Before adding a new release name, check the `Release Naming` tables in all
  four repos to avoid repeats.

| Due date | Base name | Source subject |
| --- | --- | --- |
| April 1, 2026 | Axolotl Array | Axolotl |
| May 1, 2026 | Monarch Maze | Monarch butterfly |
| June 1, 2026 | Jaguar Junction | Jaguar |
| July 1, 2026 | Saola Sandbox | Saola |
| August 1, 2026 | Orangutan Obstacle | Orangutan |
| September 1, 2026 | Numbat Nexus | Numbat |
| October 1, 2026 | Dhole Dilemma | Dhole |
| November 1, 2026 | Kakapo Knot | Kakapo |
| December 1, 2026 | Vaquita Vault | Vaquita |
| January 1, 2027 | Pangolin Puzzle | Pangolin |
## Keep This File Up To Date

Update this file whenever contributor workflow changes, especially when setup
commands, validation commands, audit scripts, or public API expectations
change.
