# Working on Infernal Machine

A Magic: The Gathering Commander engine in Python (`infernal_machine/`, tests in `tests/`, no dependencies, Python 3.11 and up).
The README and the pages in `docs/` describe what the engine does; this file is how to change it.

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
   dataclass, with `resolve(game, controller, target)`). The effect dataclasses themselves are in `effects/families/` (`copying`, `tokens`,
   `counters`, `mana`, `life_and_damage`, `library_and_hand`, `exile_and_return`, `destroy_and_sacrifice`, `combat_and_pump`, `votes`,
   `turns_and_control`, `spells_and_misc`): put a new one with its kind and import it into `outcomes.py` by name. An effect that acts on something of its ability's context (the source, the permanent that set a trigger off, the player, the previous
   target) says which with one class attribute, `binds = SOURCE` (`effects/targets.py`: `SOURCE`, `SUBJECT`, `DEAD_SUBJECT`,
   `SOURCE_AND_SUBJECT`, `DEAD_SOURCE`, `PLAYER`, `PREVIOUS_TARGET`); the resolver and the trigger checks both read it. A sentence that only qualifies the one before it
   ("... draw two cards instead.", "That token gains haste.") is read as a private marker effect and folded into the effect before it by one `Follow` row in a
   table at the end of `outcomes.py` (`effects/follow.py`), not by a new `_merge_*` branch. Triggers are in `effects/triggers.py`, static abilities in
   `effects/statics.py`, activated abilities in `effects/activated.py`, costs in `effects/costs.py`, mana abilities in `effects/mana.py`.
2. **Declare the event** in `effects/events.py` (`declare(name, pattern, ...)`) if it is a new trigger. `Game.trigger` and
   `Game.happened` accept only declared events; `tests/test_events.py` enforces it. An event that concerns only some hearers or occasions says which with `accepts=` (a callable
   `(hearer, subject, facts) -> bool`, e.g. `fact("second")`, `about_artifact`, `on_the_subject`), not with a new branch in `happened`.
3. **Export it** from `effects/__init__.py` (explicit lists) if it is a new public name.
4. **Do the work in `Game`** (`game.py`; combat is `combat.py`, paying for things with mana is `payment.py`, casting a spell is `casting.py`, and playing or casting from a zone other than the hand is a `ZonePlay` in `zones.py`: add one class and list it in `ZONE_PLAYS`, and the legal actions, the dispatch, the bot and the goldfish all see it).
   *Asking the player:* a question to a player is a typed prompt (`prompts.py`): a `PromptKind("clone", "Choose what to copy for ")` constant, asked as `choose(CLONE_PROMPT(name), options)`
   and recognised with `CLONE_PROMPT.matches(prompt)`, which compares the kind's name, not the wording. A `Prompt` is still a `str`; the server sends its `kind` and `subject` beside the text. Never take a prompt apart by its words (`startswith`, `==`, `removeprefix`): use `KIND.matches`, `is_one_of`, `subject_of` (`tests/test_prompts.py` fails on it).
5. **Test it from the card's real Oracle text**, never from invented wording: `tests/real.py` (`REAL`, built from
   `tests/real_oracle_texts.json`) or `real(name, cost, type_line, text, power, toughness)`. Play the card through the game
   (`table3`, `script`, `run_stack`, `lands`, `pick`, `BEAR`, `OGRE`), include a case where the effect must not apply, and check the
   new guards by mutation: undo the guard and see a test fail. The shared fixtures are in `tests/helpers.py`: import them from there,
   never from another test file. Name a new test file for the behaviour (`test_ninjutsu.py`), not the issue number.
6. **Add a bullet to `docs/card-effects.md`** (the "Card effects" section).

Cite the Comprehensive Rules in a comment where a rule is applied (`# CR 502.4`).

## When `Card` gains a field

Bump `CARD_FORMAT` in `cards.py`. Both card files (`.cache/oracle_bulk.json` and `.cache/cards.json`) record it and are fetched again
when it differs, instead of loading older cards with the new field's default. `examples/demo_cards.json` is hand-made and used offline
(the tests forbid the network), so it is converted, not fetched: check its cards read right with the new field's default, then set
`"format"` in the file to the new number (`tests/test_cards.py` fails until you do).

## Checks

Run before you push:

```
python -m unittest discover -s tests -t .      # CI runs this on Python 3.11 and 3.13
python tools/run_tests.py                      # the same tests across processes (about 2.5 times faster; a failure is the same failure)
python tools/coverage_audit.py --top 1         # how many Commander-legal cards are fully playable
python tools/coverage_audit.py --decks examples/decks/*.txt --baseline examples/decks/baseline.json   # the tracked decks: no card that played may stop (--write-baseline refreshes it)
                                               # a coverage pull request says what this printed before and after: the real decklists' share first, then the pool's
python tools/play_smoke.py                     # every fully playable card casts or plays without an error
python tools/explain_card.py --audit           # no card is read in a way the misparse audit knows is wrong (`explain_card.py CARD` shows how one was read)
```

CI (`.github/workflows`): `tests` (required) and its `typecheck` job (pyright: no type errors; run it with
`pip install pyright==1.1.414 && python -m pyright`; an `Optional` you know is there is unwrapped with `_checked(value)` in `game.py`), `precon report` (every card of the five precon decks must be fully playable), `tracked decks` (which also runs the misparse audit, `python tools/explain_card.py --audit`: no card may be read wrongly in a way a rule knows; the decks in `examples/decks` against `baseline.json`: a card that played may not stop; every pull request that touches the engine, and Mondays, when it also updates one comment on the roadmap epic #453),
`bot games` (120 four-player bot games between the precon decks, none may raise; seed `g` is game `g`; it runs on every pull request, and
its job `bot games (all shards)` is the one to require next to `tests`), `coverage audit` (weekly, a measurement that never fails), and `bot strength` (weekly: the default bot against the plain bot on the precon decks, 480 duels in six shards; it fails only if the whole 95% interval is below 50%, i.e. a change made the bot reliably worse; each shard takes about a minute on GitHub's runners, and the first run (2026-10-15) won 310 of 480, 64.6% (60.2%-68.7%); run it by hand with `python tools/compare_bots.py examples/precons/*.txt`, or on GitHub with `gh workflow run "bot strength"`).

A change meant to leave play untouched (a speed pass, a refactor) is checked by replaying seeds: `python tools/replay_check.py record FILE`
on `main`, then `python tools/replay_check.py check FILE` on the branch hashes every event of 24 four-player games and fails if any game
differs, and prints the CPU speed ratio. The tests run with `Game.verify_views` on, which fails a change that bypasses the epoch counter
behind `Game._board_view` (mutate `seat.battlefield`/`graveyard` and `Permanent.card`/`attached_to` the ordinary way).

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

The analysis behind these tools (mechanisms, families, the ranking, `analyze_decks`, the baseline compare) is `infernal_machine/coverage.py`;
`tools/coverage_audit.py` is the command line over it (fetching the pool, printing markdown), and package code such as `analyze` imports the same functions.

`python tools/coverage_audit.py --mechanisms --next` ranks the work by how much each piece unlocks, weighted by how played the cards
are; `--mechanism NAME` lists the unsupported wordings inside one mechanism or family. The backlog is tracked in issue #219.

`_TEMPLATES` is read in order, so its order is part of the meaning. `python tools/template_audit.py` lists the templates no sentence in
the pool reaches and the sentences two templates read differently (the first listed wins); run it after reordering or adding a broad
template.
