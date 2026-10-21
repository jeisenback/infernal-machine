# Real decklists for the coverage audit

Three Commander decks that people actually play, used to aim the card-coverage work (issue #428). They are the EDHREC "average deck"
for each commander (public pages, copied as plain card lists on 2026-10-18): the 99 cards most often played with it, so a typical
list, not any one player's. They are **not** in the gauntlet and are not meant as opponents.

| File | Commander | Style |
|---|---|---|
| `atraxa_edhrec_average.txt` | Atraxa, Praetors' Voice | proliferate and poison, four colors |
| `ur_dragon_edhrec_average.txt` | The Ur-Dragon | Dragon tribal, five colors |
| `krenko_edhrec_average.txt` | Krenko, Mob Boss | Goblin tribal, mono red |

```
python tools/coverage_audit.py --decks examples/decks/*.txt        # what blocks them, and what to build first
```

## Modelled decks (`*_modelled.txt`)

Ten more commanders are tracked as *modelled* decks, not real lists: `modelled.json` names each commander (or partner pair) and a few core
cards, and `tools/model_deck.py` fills the rest of the 100 cards from the card pool (Commander-legal, the commander's colors, most played
first by Scryfall's EDHREC rank, 36 lands). Nobody exported them, so they are a model of a typical deck, like the audit's own.

```
python tools/model_deck.py examples/decks/modelled.json        # rewrites the *_modelled.txt files from .cache/commander_pool.json
```

Read the numbers with that in mind: the modelled decks are 93-99% playable and the three real EDHREC averages 74-80%, because ranking by
popularity picks the cards the engine already plays (the top 500 cards are 92% playable). They guard against regressions in the baseline; the
real lists are the ones to aim new work at, so the audit's headline is the real lists' share, with the modelled decks' share and the total
beside it (a deck is "modelled" by its `_modelled` name). Replace a modelled deck with a real export (`tools/import_deck.py`) whenever you have one.
Banned cards named as core (Mana Crypt, Dockside Extortionist) are left out and reported.

## The baseline (#475)

`baseline.json` keeps, for each deck here, the names of the cards the engine cannot play yet. It is how the tracked decks stay honest:

```
python tools/coverage_audit.py --decks examples/decks/*.txt --baseline examples/decks/baseline.json        # exit 1 if a card that played no longer does
python tools/coverage_audit.py --decks examples/decks/*.txt --write-baseline examples/decks/baseline.json  # refresh it after building something
```

A card that played in the baseline and does not now is a regression (a parser change, or a card whose Oracle text changed) and fails the
check, naming the card. A card that now plays is only a reminder to refresh the file. A deck with no entry is recorded, not failed; an entry
whose deck was not checked fails (a deck file that went missing must not read as "nothing got worse"). Every coverage pull request reports the
decks' playable share next to the pool's, and refreshes the baseline in the same commit as the cards it unlocks.

The `tracked decks` workflow (`.github/workflows/tracked-decks.yml`) runs that check on every pull request that touches `infernal_machine/` or these
decks, and every Monday. A regression, a baseline deck that was not checked, or a deck file that cannot be read fails it. The Monday run also
keeps one comment up to date on the roadmap epic (#453) with each deck's share and the five pieces of work that unlock the most cards.

The audit reports each deck's playable share and ranks the pieces of work by the cards they unlock across all of them. Re-run it after
each piece. Playable share (cards the engine fully reads): before #428 work 73 / 300 cards of Atraxa, 64, 66 for Krenko and Ur-Dragon
(68% together); after the first round 79, 71, 68 (73%); after the second 79, 73, 71 (74%); on 2026-10-21, after the library search family (#495),
80, 75, 74 (76%). To add a list, export one from a deck site and run it through `tools/import_deck.py`.
