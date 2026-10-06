---
name: pr-body
description: Use when asked to open or write a pull request for Infernal Machine. Gives the section layout, when to say Closes versus Part of, and the facts that must be real.
---

# PR body

Open a PR only when the user asks. Check for a PR template first (`.github/pull_request_template.md`); if one exists, use its headings. Otherwise use this layout.

```
Closes #N.            or:   Part of #N (what remains).

## What
- One bullet per behaviour, in the terms of the card text or rule it reads.

## Not done
- What a reader might assume is included and is not.

## Tests
- N new tests in tests/test_<name>.py; full suite M tests pass.
- Mutation checks (K): each thing broken, and that a test failed.
- 100 four-player bot games with <cards> in every deck: all finished, avg T turns.

## Merge notes
- Branched from the default branch, so it does not include #X.
- Files likely to conflict with open PRs.
```

Rules:

- **Closes only when the issue is whole.** If any listed item is left, write "Part of #N" and say what remains.
- **Numbers are real.** Quote the counts from the last run on this commit. If a step was skipped (no bot games, no mutation checks), say so. Do not write "all tests pass" without a count.
- **Name the bugs the tests caught** and any behaviour change to existing play.
- **Texts from memory.** List the cards whose text was not checked against Scryfall.
- **Merge notes.** Run `git branch -r` and the GitHub tools to list open PRs. Name the usual hotspots if touched: the `_parse` return line, the template list and trigger loop in `effects.py`, the `become_monarch` area in `game.py`, and the README support list.
- End with the attribution lines the session gives. No emojis.
