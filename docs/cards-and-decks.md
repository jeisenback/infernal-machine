# Cards and decks

Where cards come from, what makes a deck legal, and the files cards are cached in.

## Pulling cards

```python
from infernal_machine.cards import CachedSource, ScryfallSource, load_deck

source = CachedSource(ScryfallSource(), ".cache/cards.json")
bolt = source.get("Lightning Bolt")
deck = load_deck(open("deck.txt").read(), source)  # deck.commanders, deck.main, deck.sideboard
```

- `ScryfallSource` calls the [Scryfall API](https://scryfall.com/docs/api). Single
  lookups use `/cards/named`, and decklists use `/cards/collection` in batches of 75.
  It sends the required headers and spaces requests 100 ms apart.
- `CachedSource` wraps any source and stores the cards it fetches in a JSON file,
  so repeat lookups work offline.
- `BulkSource(".cache/oracle_bulk.json")` skips the per-card API calls. It downloads Scryfall's
  [Oracle Cards bulk file](https://scryfall.com/docs/api/bulk-data) (~25 MB gzipped, ~35,000 cards) once, saves a
  slim copy, and refreshes it after a week (keeping the old copy if Scryfall is unreachable). Everything after
  that is offline. The server uses it with `--bulk .cache/oracle_bulk.json`.
- `parse_decklist` reads Arena/MTGO/Moxfield text: `Commander` / `Deck` / `Sideboard`
  headers, `1 Sol Ring (CMM) 400`, and Moxfield's `*CMDR*` and `*F*` tags.

### Decks from Moxfield or Archidekt

```
python tools/import_deck.py EXPORT.txt -o my_deck.txt [--check]
```

Neither site has a public API to fetch from: Moxfield has none and turns bots away, and Archidekt's open JSON is unofficial and its
terms forbid scripted requests. So the engine makes no request to them; you export the list yourself (Moxfield: the deck's Export, as
text; Archidekt: Export, as text or CSV) and `tools/import_deck.py` turns it into a decklist. It drops set codes, collector numbers,
`[Category]` and `^Tag^` annotations and foil marks, adds up repeated cards, finds the commander (a `Commander` section, `*CMDR*`, or
the `[Commander]` category, or the one card alone after the sideboard of a 99-card Moxfield export, which it says it assumed), keeps a sideboard, leaves a maybeboard out, and says what it dropped. It warns when a 100-card list has no
commander. With `--check` it loads the result from the card file, offline, and reports cards it can't find and the deck's Bracket
floor.

### The saved gauntlet

`examples/gauntlet.json` lists a few decks to play against, each with the Commander Bracket floor of its cards and its commander (the
five Secrets of Strixhaven precons are the start, all at Bracket 1). `matchup`, `analyze`, `compare` and `impact` use them when you
name no opponents, and `--max-bracket N` (on `matchup` and `analyze`) picks among them without loading any:

```
python -m infernal_machine.gauntlet                    # list them
python -m infernal_machine.gauntlet --add deck.txt     # copy a decklist in with its Bracket floor and commander
python -m infernal_machine.gauntlet --check            # the saved floors still match the cards (CI runs this)
```

Every saved deck is at Bracket 1 today, so `--max-bracket` cannot yet separate weak tables from strong ones: `--add` an imported
Bracket 3 deck to give it something to choose between.

## Commander deck rules

```python
from infernal_machine.commander import deck_problems

for problem in deck_problems(deck):
    print(problem)
```

`deck_problems` returns every rule a deck breaks. An empty list means the deck is legal. It checks:

- The deck has exactly 100 cards, counting the commanders.
- The commander is a legendary creature or says it "can be your commander".
- Two commanders are allowed when they pair: Partner, Partner with, Partner—X,
  Friends forever, Choose a Background, or Doctor's companion.
- Singleton, except basic lands and cards that allow more copies (Relentless Rats, Seven Dwarves).
- Every card fits within the commanders' combined color identity.
- Banned cards are flagged, using Scryfall's Commander legality.

## Deck stats

```python
from infernal_machine.analysis import analyze

stats = analyze(deck.commanders + deck.main)
stats.land_count, stats.average_mana_value, stats.curve, stats.color_pips
```

- `curve` counts nonland cards by mana value, with 7+ in one bucket.
- `average_mana_value` also leaves out lands.
- `color_pips` counts colored mana symbols across all costs. Hybrid symbols count toward both colors.

## Standard

The engine plays Standard as well as Commander. A format (`formats.py`: `COMMANDER`, `STANDARD`) sets the starting life, the deck
size and the copy limit; `Game(seats, seed, format=STANDARD)` starts at 20 life with no command zone, commander tax or commander
damage. A two-player game already follows the two-player rules: the player who goes first skips their first draw (CR 103.8a) and
no mulligan is free (CR 103.5c).

- **Deck rules (`formats.deck_problems(deck, STANDARD)`):** at least 60 cards in the main deck, at most 15 in the sideboard, no more
  than four copies of a card counting the sideboard (basic lands, and cards that say "a deck can have any number of cards named",
  have no limit), every card Standard-legal on Scryfall (`Card.standard_legal`), and no commander. Commander decks are checked as before.
- **Which format a table plays:** `format_of(decks)` is Commander if every deck has a commander and Standard if none does; mixing the
  two is an error. `matchups` and the simulation tools use it, so a 60-card list with no commander goes through `simulate`, `tune`
  and `matchup` as it is.
- **The server:** `python -m infernal_machine.server --format standard` checks every human and bot deck against Standard.
- **Not there yet:** best-of-three with sideboarding (the sideboard is read and checked but not used in play), and a legality list
  that follows rotation other than through Scryfall's own `legalities.standard`. Cached cards from before this change are fetched again
  (see "The card caches" below).

## The card caches

Cards are looked up through one of two cache files, both under `.cache/` and both safe to delete:

- `oracle_bulk.json` (`BulkSource`): Scryfall's bulk Oracle Cards data, downloaded once and refreshed after a week.
- `cards.json` (`CachedSource`, the server's default): the cards fetched one by one from the Scryfall API.

Each file records `CARD_FORMAT`, the version of the `Card` fields. When the engine adds a field to `Card` (Standard legality, Game
Changers) it bumps that number, and a file saved in another format, or the older bare mapping with no format at all, is fetched
again the next time a card is needed, rather than loaded with the new field's default (which would call every old card legal in
Standard and no card a Game Changer). Nothing is lost but one round of lookups; offline play works from the files that are current.
`examples/demo_cards.json` is a hand-made cache of this kind that ships with the repository for offline games.
