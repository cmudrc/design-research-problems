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

- Keep homepages in this order: title, tagline, what it does, highlights, typical workflow, ecosystem integration, start here.
- Use concise research-oriented prose.
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
