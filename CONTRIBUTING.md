# Contributing (Internal)

This file documents the minimal internal workflow for maintainers of
`pyads-agile`.

## Scope

- This repository is maintained for internal and product needs.
- Unsolicited external pull requests are not part of the normal workflow.
- Releases follow independent Semantic Versioning (`MAJOR.MINOR.PATCH`).

## Internal Workflow

1. Create a branch from `main`.
2. Implement the change with focused commits.
3. Run tests relevant to your change.
4. Update docs/changelog when behavior or API changes.
5. Open an internal PR for review and CI.
6. Squash/merge after approval.

## Testing

Run the default test suite:

```bash
pytest
```

Run real-target integration tests when applicable:

```bash
pytest tests/integration_real --ads-target=real
```
