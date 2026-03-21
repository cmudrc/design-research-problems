# Documentation Maintenance

## Build Docs Locally

- `make docs-check`
- `make docs-build`

## Example Page Generation

Example pages are generated from runnable scripts via `scripts/generate_example_docs.py`.
Keep example docstrings accurate and rerun docs checks after updates.

## Docstring Style

Use Google-style docstrings where policy applies.
Run `make docstrings-check` before merge.

## Page-Writing Conventions

- Keep the homepage short: title, tagline, concise framing, quickstart callout, section-oriented links, and only the minimum ecosystem/contribution notes needed for orientation.
- Keep the root hidden home-page toctree section-first so the PyData header and sidebar stay stable.
- Emphasize stable problem-family APIs, benchmark metadata, and reproducible evaluation contracts.
- Prefer stable problem-family language over ad-hoc naming.

## Table vs Prose Rule

Prefer compact tables for scanning. Preserve nuance in narrative paragraphs directly below the table. Do not use tables to carry long explanatory sentences.

## Cross-links

Use `:doc:` for internal links and include sibling-library context when a page depends on external orchestration or analysis.

## API Page Updates

When public exports change, update:

- `docs/api.rst`
- family/concepts references
- quickstart/examples snippets
