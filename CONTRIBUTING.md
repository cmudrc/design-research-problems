# Contributing

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
make dev
```

For the optional local `TrussMe` integration:

```bash
make install-trussme-local
```

## Common Commands

```bash
make test
make qa
make ci
make docs
```

## Notes

- Keep the public API curated and intentionally small.
- Prefer package resources for catalog content instead of embedding long prompts in Python modules.
- New problem families should add tests, docs, and at least one runnable example.
