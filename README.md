# Infernal Machine

A Magic: The Gathering engine, starting with the Commander format.
Python 3.11+, standard library only.

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
- `parse_decklist` reads Arena/MTGO/Moxfield text: `Commander` / `Deck` / `Sideboard`
  headers, `1 Sol Ring (CMM) 400`, and Moxfield's `*CMDR*` and `*F*` tags.

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

## TCP players

The engine talks to players through the `Player` protocol (`notify`, `choose`).
`TcpPlayer` implements it for remote clients:

```python
from infernal_machine.tcp import accept_players, listen

server = listen("0.0.0.0", 4000)
players = accept_players(server, count=2)
players[0].choose("Keep this hand?", ["Keep", "Mulligan"])
```

Each message is one JSON object per line:

| Direction | Message |
|---|---|
| client -> server | `{"type": "hello", "name": "Alice"}` (must come first) |
| server -> client | `{"type": "welcome", "seat": 0}` |
| server -> client | `{"type": "event", ...}` (no reply) |
| server -> client | `{"type": "choose", "id": 1, "prompt": "...", "options": ["Keep", "Mulligan"]}` |
| client -> server | `{"type": "response", "id": 1, "choice": 0}` |
| server -> client | `{"type": "error", "message": "..."}` (after bad input the prompt is sent again) |

You can connect by hand with `nc localhost 4000`.

## Tests

```
python3 -m unittest discover -s tests -t .
```
