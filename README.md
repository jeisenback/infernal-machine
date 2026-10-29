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

A fourth workflow (`.github/workflows/coverage-audit.yml`) runs every Monday and by hand. It runs `tools/coverage_audit.py`, which fetches every Commander-legal paper card from Scryfall's search API (kept in `.cache/commander_pool.json` for a week), and writes a step summary: the share of cards the report finds fully playable, by card type and by EDHREC rank, and the unsupported lines found on the most cards or as a card's only gap. `--format NAME` audits the cards legal in another format (the pool is fetched with Scryfall's `legal:NAME` search and kept in `.cache/NAME_pool.json`); EDHREC's rank is Commander's play data, so for Standard there is no rank table or typical deck, every card counts one, and the weekly workflow posts the Standard tables beside Commander's, and, when the workflow is run by hand, a job of its own posts one line for each of Pauper, Pioneer, Modern, Legacy and Vintage (the share of its pool that plays, #522; about 25 runner-minutes, so not every Monday); the fifteen real Standard lists in `examples/decks/standard` (one per top archetype of MTGGoldfish's paper metagame, dated) are held to their own `baseline.json` by the `tracked decks` workflow, whose Monday comment on the roadmap epic carries their headline beside Commander's. Their ranking is printed twice: by the cards unlocked, and weighted by each archetype's metagame share, read from the first line of its list (a list without one weighs 1; the Commander lists have none and keep the count order), so the pieces that unlock cards in the decks people play come first while the headline and the baseline stay count-based (#565). It never fails on gaps; it is a measurement, and the backlog it feeds is tracked in issue #219. The same workflow runs `tools/template_audit.py`, which lists the rules-text templates no card in the pool reaches and the sentences that more than one template reads (the order of `_TEMPLATES` decides which wins), also as a step summary. The numbers are also uploaded as `coverage-audit.json`. With `--mechanisms` it also groups the gaps by mechanism (a keyword or ability word, or the first of a list of rules-text patterns that matches), sorted by the cards in the EDHREC top 5000 for which that mechanism is the only gap, which is the list to pick the next piece of work from (an "All cards" column counts every card with a line in the mechanism, playable or not, so each row shows how much of it is already covered); `--mechanism NAME` lists the unsupported wordings inside one mechanism or family. `--next` ranks the pieces of work: a family is a keyword or ability word or one of a maintained list of repeated wordings (add one when a drill-down shows it), a card with a line no family covers is never counted as unlocked, and the greedy order assumes each family above a row is built and weighs a card by the chance a typical deck holds it, a modelled inclusion probability that falls with EDHREC rank (a deck of 99 cards with 17 basic lands assumed), so a row says how many cards per deck it makes playable and what share of a typical deck is playable after it. The same model gives the headline number in the audit, the share of a typical 100-card deck that is fully playable and the chance that all of it is, which the weekly step summary tracks; it is an assumption about the shape of a deck, not data, so it is a figure to watch from week to week. The patterns are a heuristic, so the groups guide the choice and are not exact counts. The same workflow then runs `tools/play_smoke.py`, which casts or plays every card the report calls fully playable in a small game, activates up to three of its abilities and lists any that raise an error or take more than five seconds; understanding a card's text and playing the card are different things, and this checks the second at the level of "does not crash or hang". `tools/combo_smoke.py` does the same for combos: it reads the combos in the Commander Spellbook cache (`.cache/combos.json`, filled by `analyze` and `tune`), and for each one whose pieces are all fully playable puts them on a table, takes the first cast or activation the game offers up to 40 times, and lists any that raise or take more than a minute. It is run by hand, since the cache is local; it lists the combos that ended the game or ran to the board limit, and `--all` shows each combo's outcome. A gap never fails the run. `tools/combo_lines.py` runs the loops: for each combo a tracked deck holds, it starts the pieces where Commander Spellbook's steps say they begin, takes the actions the steps name round after round, and prints a table of what the engine did (the opponent lost, the loop ran and what a round left behind, or the action that was not offered and in which round). It is a measurement too, and never fails. `tools/ability_smoke.py` checks the costs: for each activated ability of each fully playable card whose cost is a sacrifice, a discard, an exile from the graveyard, removed counters, tapped creatures or life, it builds a table that can pay it, checks the game offers the activation, performs it and checks the cost was paid (what the audit's "fully playable" does not say: that the card can do what it says). It lists abilities that are not offered, raise, hang or leave a cost unpaid, and counts by name the costs it builds no table for (crew, loyalty, "Activate only if ...", a target on the stack or in combat, abilities from the hand). The weekly coverage workflow runs it beside `play_smoke`. Two rules keep "fully playable" honest: a line that is several triggers ("When this enters and whenever ...") counts only if every one of them is understood, and a card whose second face or half the engine cannot play (an Adventure, the other half of a split card, a back face that is not a land) is listed with the problem "Second face or half of the card ... not playable".
