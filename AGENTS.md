# AGENTS.md

## Purpose

This repository is the Python 3.12+ benchmark-task layer in the
CMU Design Research Collective design-research ecosystem. It spans text,
decision, optimization, grammar-based, and MCP-facing workflows. Keep
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

## Release Planning

- Do not create monthly milestone naming tables, themed release PR names, or
  calendar release branches as default maintenance.
- Prefer small issue/PR-scoped planning and package version releases driven by
  user-facing changes.
- Use GitHub milestones only for explicit, short-lived initiatives with an
  active owner; they are optional scheduling aids, not release gates.
- Name release branches and release PRs for the version or concrete change set
  they contain.
- When publishing, update package metadata, docs, examples, and GitHub
  Releases/PyPI notes as needed. Do not add README callouts that point to
  monthly milestones.
## Keep This File Up To Date

Update this file whenever contributor workflow changes, especially when setup
commands, validation commands, audit scripts, or public API expectations
change.
