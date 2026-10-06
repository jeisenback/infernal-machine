# Infernal Machine

A Magic: The Gathering engine, Commander first. Python 3.11+, standard library only. Rules and supported mechanics are in `README.md`.

## Before changing code

- Read `.claude/heartbeat.json` first. If it shows another session active on the same branch (updated in the last few minutes), stop and tell the user instead of editing.
- Write it when starting a task and update it at each step (before edits, after tests pass, after commit and push). Mark it `done` at the end. It is git-ignored; never commit it.
- Fields: `branch`, `issue`, `task`, `step`, `files`, `status`, `updated` (UTC).

## Code

- Standard library only. Do not add dependencies.
- A card is playable whole or it is unsupported. A text that only half parses leaves the card unsupported and shows in `python -m infernal_machine.report DECKLIST`. Never play half a card.
- Keep it small: build what the issue asks for, nothing extra.
- No emojis anywhere (code, text, docs, commits).

## Tests

`python -m unittest discover -s tests -t .` runs everything. Run it in full before pushing.
`python tools/bot_games.py DECKLIST --games 100 --cache examples/demo_cards.json` plays four-player bot games and fails if any does not finish with a winner. Run it when a change touches turn flow, combat, the stack or bot decisions.

## Skills

- `add-mechanic`: adding or extending a rules mechanic.
- `pr-body`: writing a pull request description.

## Git

- Work on the branch named in the task. Open a PR only when asked.
- Commit subjects say what the change adds, in one line. Commits and PR bodies follow the attribution lines the session gives.
