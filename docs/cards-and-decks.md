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

### What blocks your deck

```
python tools/coverage_audit.py --decks my_deck.txt [other_deck.txt ...] [--top 15]
```

The coverage audit ranks engine work by a modelled deck; this asks the same question of your decks. It reads the decklists and the card
file (offline), counts every copy of every card, and reports how many cards each deck can play, the pieces of engine work in the order that
unlocks the most of them (each assuming those above it are built, with the share of the decks playable after each), the kinds of text
the unplayable cards have, and each unplayable card with its first unsupported line. A line that no maintained family covers is its own
piece of work, named by its wording, so a deck of one-off cards shows a long list that unlocks one card each, which is the honest answer:
the first deck tried this way (a 100-card Bracket 4 list) had 41 unplayable cards and no single piece of work that unlocked more than two.
Several decks are ranked together, so work that several of them need comes first.

### The saved gauntlet

`examples/gauntlet.json` lists a few decks to play against, each with the Commander Bracket floor of its cards and its commander (the
five Secrets of Strixhaven precons are the start, all at Bracket 1). `matchup`, `analyze`, `compare` and `impact` use them when you
name no opponents, and `--max-bracket N` (on `matchup` and `analyze`) picks among them without loading any:

```
python -m infernal_machine.gauntlet                    # list them
python -m infernal_machine.gauntlet --add deck.txt     # copy a decklist in with its Bracket floor and commander
python -m infernal_machine.gauntlet --check            # the saved floors still match the cards (CI runs this)
```

Every saved Commander deck is at Bracket 1 today, so `--max-bracket` cannot yet separate weak tables from strong ones: `--add` an
imported Bracket 3 deck to give it something to choose between.

**Standard.** Each saved deck has a format, and a deck is played against decks of its own: with no opponents named, a deck with no
commander gets the saved Standard decks (a Standard deck has no Bracket, so `--max-bracket` never leaves one out). There are five, one
per color, built by `tools/build_standard_decks.py` from the card file by a fixed recipe: 24 basic lands, 36 spells (four copies of the seven
best mono-colored creatures and the two cheapest removal spells that destroy or damage a target creature, scored by size for the cost
and combat keywords) and a fifteen-card sideboard. They are **baselines, not decks anyone plays**, made so a Standard deck has something
to play against; they are also only as current as the card file's legality data. `gauntlet --check` holds each to the Standard deck rules
(60 cards, at most 15 in the sideboard, four copies, every card marked Standard-legal), to having no commander, and to every card of the
main deck and sideboard being one the engine plays completely. `gauntlet --add DECKLIST` saves a deck with no commander as a Standard deck
(refusing one that breaks those rules), and `--format standard` lists them.

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

### Brawl, Duel Commander and Oathbreaker

The same checks, with each format's own numbers, through `formats.deck_problems(deck, fmt)`:

| | cards | life | commander damage | a card must be legal in | commander |
|---|---|---|---|---|---|
| Commander | 100 | 40 | 21 | Commander | legendary creature (or partners) |
| Brawl | 60 | 25 (30 with more than two players) | 21 | Standard | legendary creature **or planeswalker** |
| Duel Commander | 100 | 20 | **15** | Duel Commander (its own banned list) | as Commander |
| Oathbreaker | 60 | 20 | **none** | Oathbreaker (its own banned list) | any planeswalker, plus a signature spell |

A deck says which format it is played in with `Deck.format` (`formats.with_format(deck, "brawl")`, or `--format brawl|duel|commander|standard`
on `matchup`, `compare`, `impact` and `analyze`). One that does not is Commander if it has a commander and Standard if it does not:
Brawl and Oathbreaker are 60 cards and Duel Commander has Commander's 100, so none of them can be told from its shape and all are asked for
by name. Every deck
at a table must be in the same format, and a Brawl or Duel Commander deck must have a commander. The game uses the format's starting
life and commander-damage limit (the bot is told the limit and aims its commander by it); the Commander Brackets are Commander's, so
`analyze` leaves that section out for the others. Duel legality comes from Scryfall's `duel` legality, kept on each card as `duel_legal`
(so the card file was fetched again when it was added). There are no saved Brawl or Duel Commander decks to play against by default:
name opponents.

**Oathbreaker** (`oathbreaker.py`). A deck is 60 cards: an Oathbreaker (any planeswalker, in `Deck.commanders`), a signature spell
(an instant or sorcery, in `Deck.signature_spell`; decklist sections `Oathbreaker` and `Signature Spell`) and 58 others, singleton, all in
the Oathbreaker's color identity, signature spell included, and legal in Oathbreaker (`Card.oathbreaker_legal`, Scryfall's `oathbreaker`
legality, so `CARD_FORMAT` is 6). In the game both start in the command zone and work like a commander: two more to cast for each earlier
cast, and back to the command zone instead of the graveyard, exile, hand or library. The signature spell is offered only while its owner
controls their Oathbreaker (a permanent of that name), at the timing its type gives. There is no commander damage: nothing is recorded and the
seats are told no limit. The bot casts the Oathbreaker first like a commander, and the signature spell like any other spell, so it holds
a signature removal spell for a creature worth it.

### Companions

A deck names a companion in a `Companion` section of its decklist (`Deck.companion`; `tools/import_deck.py` keeps a `Companion` section or
a `[Companion]` category apart from the deck). `formats.deck_problems` checks it for every format, from `companion.py`: the card has the
companion ability, the starting deck (the commanders and the main deck) meets the condition on its companion line, and the deck has at
most one. The ten companions the card file has (Gyruda, Jegantha, Kaheera, Keruga, Lurrus, Lutri, Obosh, Umori, Yorion, Zirda) are checked
by their wording; a companion with any other condition is reported as one that cannot be checked, not passed. In a commander format the
companion is outside the 100 (or 60) cards but must be inside the commanders' color identity, not also in the deck, and legal in the
format (Yorion, which asks for twenty cards more than the minimum, cannot be played with Commander's exact 100); in Standard it is one of
the sideboard's fifteen and counts for the four copies.

In the game the companion starts outside it. At the times its owner could cast a sorcery (their main phase, nothing on the stack), once per
game, `Companion: <card>` is offered when {3} can be paid: it pays and the companion goes into the hand, to be cast like any card
(CR 702.139). The bot takes it when it has nothing else to do with its mana, after casting what it can.

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
