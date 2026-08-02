## Summary

<!-- What does this PR change, and why? -->

## Related issue

Closes #

## Type of change

- [ ] Bug fix
- [ ] New endpoint / new field
- [ ] Refactor
- [ ] Migration / schema change
- [ ] Deployment / infra
- [ ] Chore / tooling

## Endpoints touched

<!-- e.g. GET /api/data/entities, POST /api/auth/login. Write "none" if not applicable. -->

## How to test

<!-- Steps a reviewer can follow against a local server (python app.py --port 5000). -->

1.
2.
3.

## Checklist

- [ ] `pytest` passes (`cd api && pytest -c tests/pytest.ini`)
- [ ] Responses use `success_response` / `error_response` from `routes/main.py`
- [ ] Logic lives in `services/` and DB access in `repositories/` — routes only handle request/response
- [ ] `api/docs/` updated if an endpoint's contract changed
- [ ] Migration generated (`flask db migrate`) and applied cleanly (`flask db upgrade`), if the schema changed
- [ ] No secrets, tokens, or `.env` values committed
- [ ] Breaking changes for `Erup` / `Brendex` are called out above, with issues opened there

## Notes for reviewers

<!-- Anything non-obvious: perf implications, data backfill needed, order of deploy. Delete if none. -->
