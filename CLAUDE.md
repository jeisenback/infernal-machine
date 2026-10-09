# infernal-machine

A Magic: The Gathering engine in pure Python (3.11+, no dependencies).

## Tests

```
python3 -m unittest discover -s tests -t .
```

Tests use `unittest`, not pytest. Real card fixtures live in `tests/real_oracle_texts.json` and load through `tests/real.py` (`REAL["Card Name"]`). After refreshing that data, run `python3 tools/audit_real_text.py` from the repo root.

## Conventions

- Branch from main. Commit messages look like `feat(engine): what it does (#issue)`; also `fix(...)`, `docs:`, `chore:`.
- Features come per GitHub issue number; reference it in the commit and add a README section for it.
- Check `.heartbeat` (local, untracked) before changing code: if it names another live session on the same task, stop and ask.
