# Working on Infernal Machine

A Magic: The Gathering Commander engine in Python (`infernal_machine/`, tests in `tests/`, no dependencies, Python 3.11 and up).
The README describes what the engine does; this file is how to change it.

## Before you change code

- Look for `.heartbeat` in the checkout. It is a local, untracked note of what a session is doing here: `session`, `branch`, `task`,
  `status`, `updated` (UTC), one per line. If it names another session's unfinished task on a different branch, stop and ask.
  Write it when you start a piece of work, keep `status` current, delete it when the branch is pushed. It is never committed (it is
  in `.gitignore`): a committed copy goes stale on `main`, as the `sweep-151` one did.
- Other checkouts are visible only through GitHub. List the open pull requests and `claude/*` branches before you start.
- One pull request per piece of work (a mechanic, a fix), from its own branch off `main`, merged with a merge commit.
  Write `Closes #N` in the body when it finishes an issue.

## How a card gets supported

A card is "fully playable" only if every line of its text is understood: `infernal_machine.report.unsupported_lines(card)` is empty.
To add a line:

1. **Parse it.** A sentence of effect text is a template in `effects/outcomes.py` (`_TEMPLATES`: a regex and a builder for an effect
   dataclass, with `resolve(game, controller, target)`). Triggers are in `effects/triggers.py`, static abilities in
   `effects/statics.py`, activated abilities in `effects/activated.py`, costs in `effects/costs.py`, mana abilities in `effects/mana.py`.
2. **Declare the event** in `effects/events.py` (`declare(name, pattern, ...)`) if it is a new trigger. `Game.trigger` and
   `Game.happened` accept only declared events; `tests/test_events.py` enforces it.
3. **Export it** from `effects/__init__.py` (explicit lists) if it is a new public name.
4. **Do the work in `Game`** (`game.py`; combat is `combat.py`).
5. **Test it from the card's real Oracle text**, never from invented wording: `tests/real.py` (`REAL`, built from
   `tests/real_oracle_texts.json`) or `real(name, cost, type_line, text, power, toughness)`. Play the card through the game
   (`table3`, `script`, `run_stack`, `lands`, `pick`, `BEAR`, `OGRE`), include a case where the effect must not apply, and check the
   new guards by mutation: undo the guard and see a test fail. The shared fixtures are in `tests/helpers.py`: import them from there,
   never from another test file. Name a new test file for the behaviour (`test_ninjutsu.py`), not the issue number.
6. **Add a bullet to the README** card-effects section.

Cite the Comprehensive Rules in a comment where a rule is applied (`# CR 502.4`).

## Checks

Run before you push:

```
python -m unittest discover -s tests -t .      # CI runs this on Python 3.11 and 3.13
python tools/coverage_audit.py --top 1         # how many Commander-legal cards are fully playable
python tools/play_smoke.py                     # every fully playable card casts or plays without an error
```

CI (`.github/workflows`): `tests` (required) and its `typecheck` job (pyright; the error count may fall but not rise above
`.github/pyright-baseline`, so lower that number when a change lowers the count; plan in #309; run it with
`pip install pyright==1.1.414 && python -m pyright`), `precon report` (every card of the five precon decks must be fully playable),
`bot games` (120 four-player bot games between the precon decks, none may raise; seed `g` is game `g`; it runs on every pull request, and
its job `bot games (all shards)` is the one to require next to `tests`), and `coverage audit` (weekly, a measurement that never fails).

Replay a failing bot game: `python tools/bot_games.py --start SEED --games 1`. It needs `.cache/oracle_bulk.json`; where the bulk
host is unreachable, build it from the cached Commander pool:

```
python - <<'PY'
import json
from infernal_machine.cards import BulkSource, Card
cards = {}
for d in json.load(open(".cache/commander_pool.json")):
    if d.get("layout") not in ("token", "double_faced_token", "emblem", "art_series"):
        card = Card.from_scryfall(d)
        cards[card.name] = card.to_dict()
json.dump({"format": BulkSource.FORMAT, "cards": cards}, open(".cache/oracle_bulk.json", "w"))
PY
```

## What to build next

`python tools/coverage_audit.py --mechanisms --next` ranks the work by how much each piece unlocks, weighted by how played the cards
are; `--mechanism NAME` lists the unsupported wordings inside one mechanism or family. The backlog is tracked in issue #219.
