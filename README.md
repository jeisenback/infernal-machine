# Infernal Machine

A Magic: The Gathering engine for Commander and Standard, with bots, simulation and deck tuning.
Python 3.11+, standard library only.

## Quick start: play a game

You can try a full game offline, with no Scryfall, using the demo cards in `examples/`:

```
# terminal 1: a table for one human and two bots
python -m infernal_machine.server --humans 1 --bots 2 --bot-deck examples/red_deck.txt \
    --cache examples/demo_cards.json --no-check

# terminal 2: join it
python -m infernal_machine.client --name Alice --deck examples/green_deck.txt
# or play in your browser instead
python -m infernal_machine.web --name Alice --deck examples/green_deck.txt
```

For real decks, leave out `--cache examples/demo_cards.json` and `--no-check`. The server then fetches cards
from Scryfall (and saves them in `.cache/cards.json`) and only seats decks that are legal Commander decks.
See [Playing over TCP](docs/server.md) for all the options.

## Tune a deck

The engine also analyzes decks: how its mana holds up, how fast it plays out, which cards earn their slot, how it does against other
decks, and whether a change makes it better. One command runs all of it and prints a report:

```
python -m infernal_machine.analyze my_deck.txt opponent1.txt opponent2.txt
```

The [tune-a-deck walkthrough](docs/tune-a-deck.md) goes through each step with example output and what to make of it. A result is only
as good as the engine's reading of the cards: it plays about a third of all Commander-legal cards completely (the most played ones far
better), and every report says when a deck holds cards it cannot play.

## Documentation

| Page | What is in it |
|---|---|
| [Tune a deck](docs/tune-a-deck.md) | A guided tour: check a deck, tune it, play it, compare a change |
| [Simulation and tuning tools](docs/simulation.md) | Reference for `analyze`, the Bracket check, the mana base, the goldfish, tuning, card impact, matchups and comparing builds |
| [Bots](docs/bots.md) | The computer player and its judgments |
| [Cards and decks](docs/cards-and-decks.md) | Where cards come from, deck rules for Commander and Standard, deck stats, the card caches |
| [Playing a game](docs/playing-a-game.md) | How a game runs, and what ends one that cannot finish |
| [Playing over TCP](docs/server.md) | Hosting a table, joining it, the protocol |
| [Card effects](docs/card-effects.md) | Every effect, trigger and keyword the engine understands, and what it cannot play yet |
| [CLAUDE.md](CLAUDE.md) | How to change the code: adding a card, the checks, CI |

## Tests

```
python3 -m unittest discover -s tests -t .
```

The same command runs on every pull request and every push to `main` (`.github/workflows/tests.yml`), on Python 3.11 and 3.13. The same workflow has a `typecheck` job that runs `pyright` over `infernal_machine/` (configured in `pyproject.toml`; installed in CI only, the engine has no dependencies). It reports no errors, and any error fails the job (it began as a ratchet at 398 errors, mostly `X | None` passed where `X` is expected, and was brought to 0 under issue #309).

A second workflow (`.github/workflows/precon-report.yml`) runs the card report on each deck in `examples/precons` and fails if any card has an unsupported line. It runs when the engine or the decks change, and every Monday, since Scryfall's Oracle text can change.

A third workflow (`.github/workflows/bot-games.yml`) plays 120 four-player bot games between the precon decks in six parallel jobs of 20 and fails if any game raises an exception. It runs on every pull request (so its result can be a required check; the one to require is `bot games (all shards)`, which fails if any shard fails or does not run), and on pushes to `main` that change the engine or the decks. Game `g` uses seed `g`, so a failing seed replays with `python tools/bot_games.py --start SEED --games 1`.

A fourth workflow (`.github/workflows/coverage-audit.yml`) runs every Monday and by hand. It runs `tools/coverage_audit.py`, which fetches every Commander-legal paper card from Scryfall's search API (kept in `.cache/commander_pool.json` for a week), and writes a step summary: the share of cards the report finds fully playable, by card type and by EDHREC rank, and the unsupported lines found on the most cards or as a card's only gap. It never fails on gaps; it is a measurement, and the backlog it feeds is tracked in issue #219. The same workflow runs `tools/template_audit.py`, which lists the rules-text templates no card in the pool reaches and the sentences that more than one template reads (the order of `_TEMPLATES` decides which wins), also as a step summary. The numbers are also uploaded as `coverage-audit.json`. With `--mechanisms` it also groups the gaps by mechanism (a keyword or ability word, or the first of a list of rules-text patterns that matches), sorted by the cards in the EDHREC top 5000 for which that mechanism is the only gap, which is the list to pick the next piece of work from (an "All cards" column counts every card with a line in the mechanism, playable or not, so each row shows how much of it is already covered); `--mechanism NAME` lists the unsupported wordings inside one mechanism or family. `--next` ranks the pieces of work: a family is a keyword or ability word or one of a maintained list of repeated wordings (add one when a drill-down shows it), a card with a line no family covers is never counted as unlocked, and the greedy order assumes each family above a row is built and weighs a card by 1 / (1 + rank / 1000) so rank 100 counts for far more than rank 4,900. The patterns are a heuristic, so the groups guide the choice and are not exact counts. The same workflow then runs `tools/play_smoke.py`, which casts or plays every card the report calls fully playable in a small game, activates up to three of its abilities and lists any that raise an error or take more than five seconds; understanding a card's text and playing the card are different things, and this checks the second at the level of "does not crash or hang". Two rules keep "fully playable" honest: a line that is several triggers ("When this enters and whenever ...") counts only if every one of them is understood, and a card whose second face or half the engine cannot play (an Adventure, the other half of a split card, a back face that is not a land) is listed with the problem "Second face or half of the card ... not playable".
