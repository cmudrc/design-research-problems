# Documentation Maintenance

## Build Docs Locally

- `make docs-check`
- `make docs-build`
- `make docs-linkcheck` when links, navigation, or landing pages change

## Example Page Generation

Example pages are generated from runnable scripts via `scripts/generate_example_docs.py`.
Keep example docstrings accurate and rerun docs checks after updates.

## Shared Docs/CI Baseline

The checked baseline and workflow ownership are documented in
`automation_baseline.rst` and enforced by `scripts/check_docs_consistency.py`.

## Docstring Style

Use Google-style docstrings where policy applies.
Run `make docstrings-check` before merge.

## Page-Writing Conventions

- Keep the homepage short: title, tagline, concise framing, quickstart callout, section-oriented links, and only the minimum ecosystem/contribution notes needed for orientation.
- Keep the root hidden home-page toctree section-first so the PyData header and sidebar stay stable.
- Keep `guides.rst` as the canonical `/guides.html` landing page and preserve
  existing top-level leaf URLs such as `/catalog_guide.html` and
  `/vscode_start.html` for compatibility.
- Keep the primary reader path in this order: installation, quickstart,
  concepts/workflow, examples, then API.
- Emphasize the five `ProblemKind` values, kind-specific APIs, benchmark
  metadata, and reproducible evaluation contracts.
- Use “problem kind” for the canonical taxonomy. Use “family” only for class
  groupings or the downstream `problem_family` compatibility field.
- Describe ideation as a catalog subset of the `text` kind, never as a sixth
  kind.

## Table vs Prose Rule

Prefer compact tables for scanning. Preserve nuance in narrative paragraphs directly below the table. Do not use tables to carry long explanatory sentences.

## Cross-links

Use `:doc:` for internal links and include sibling-library context when a page depends on external orchestration or analysis.

## Branding

- The umbrella repository owns the canonical ecosystem figure, package colors,
  and `ecosystem-topology-v1` framing. Keep this repository's vendored SVG
  byte-identical to that source.
- This repo's canonical docs brand color is `#EA8534`.
- Keep docs CSS tokens, `drc-light.png`, `drc-dark.png`, `favicon-light.ico`, `favicon-dark.ico`, and fallback `favicon.ico` aligned when updating docs styling.

## API Page Updates

When public exports change, update:

- `docs/api.rst`
- family/concepts references
- quickstart/examples snippets
- `docs/automation_baseline.rst` if workflow ownership changes
- `docs/catalog_guide.rst` if the curated family entrypoint changes
