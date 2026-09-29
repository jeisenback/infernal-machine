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

## Deck stats

```python
from infernal_machine.analysis import analyze

stats = analyze(deck.commanders + deck.main)
stats.land_count, stats.average_mana_value, stats.curve, stats.color_pips
```

- `curve` counts nonland cards by mana value, with 7+ in one bucket.
- `average_mana_value` also leaves out lands.
- `color_pips` counts colored mana symbols across all costs. Hybrid symbols count toward both colors.

## Playing a game

```python
from infernal_machine.game import Game

game = Game([(player_a, deck_a), (player_b, deck_b), (player_c, deck_c)], seed=42)
winner = game.play()
```

- **Setup:** 40 life, commanders in the command zone, shuffle, and a random starting player.
- **Mulligans:** London mulligan. The first one is free in games with 3 or more players (CR 103.5c).
- **Turns:** all twelve steps. Priority goes around the table, and a step ends only when every
  player passes in a row. There's no priority in untap or cleanup.
- **Draw:** the first player skips their first draw only in a two-player game (CR 103.8).
- **Cleanup:** discard down to seven cards.
- **Losing:** a player loses at 0 life or when drawing from an empty library.
  The last player standing wins.
- **Actions so far:** play a land (one per turn, your main phase, empty stack), cast spells, and pass.
- **Casting:** permanents, sorceries and your commander at sorcery speed.
  Instants and Flash cards whenever you have priority.
- **Paying mana:** mana is paid automatically from lands (using Scryfall's `produced_mana`) and from
  permanents with a simple tap ability: `{T}: Add {C}{C}.`, `{T}: Add {G}.`, `{T}: Add {R} or {G}.`,
  and "one mana of any color" (optionally limited to your commander's colors).
  Creatures can't tap for mana the turn they arrive. X counts as 0, and Phyrexian symbols are paid with mana.
- **Commander tax:** your commander costs {2} more for each earlier cast from the command zone.
  When your commander would go to the graveyard, you choose whether it goes back to the command zone instead.
- **The stack:** spells go on the stack and resolve last in, first out once everyone passes in a row.
- **Combat:** the active player chooses, creature by creature, whether to attack and which opponent.
  Each defending player then chooses blockers, and damage is dealt all at once. With no attackers,
  the blockers and damage steps are skipped. If any creature in combat has first strike or double strike,
  there's an extra first-strike damage step.
  - Keywords: flying, reach, vigilance, haste, defender, menace, trample, first strike,
    double strike, deathtouch and lifelink.
  - A blocked attacker deals lethal damage to each blocker in the order they blocked. Any extra goes
    to the last blocker, or to the player with trample. It stays blocked even if its blockers leave.
  - Creatures can't attack planeswalkers yet.
- **Commander damage:** combat damage from each commander is tracked per player.
  21 from one commander makes that player lose.
- **State checks:** players lose at 0 life, when drawing from an empty library, or at 21 commander damage.
  Creatures die from lethal damage (unless indestructible) or 0 toughness,
  and planeswalkers die at 0 loyalty. Damage wears off in the cleanup step.

## Card effects

`effects.py` reads an instant's or sorcery's rules text one sentence at a time. It understands:

| Rules text | Example |
|---|---|
| Draw N cards. | Divination |
| You gain N life. / Each opponent loses N life. | |
| (This spell) deals N damage to any target / target creature / target player / ... | Lightning Bolt |
| Destroy target creature / artifact / enchantment / nonland permanent / ... | Murder |
| Counter target spell. | Counterspell |
| Search your library for a basic land card, put it onto the battlefield tapped, then shuffle. | Rampant Growth |

- **Targets:** chosen when the spell is cast. If every target is gone when it resolves, the spell
  does nothing ("fizzles"). Hexproof and shroud are respected, and a spell with no legal target can't be cast.
- **Partial text:** if any sentence isn't understood, the spell still resolves but does nothing,
  and the `resolve` event is marked `"unsupported": true`. The engine never does half of what a card says.
- **Triggered abilities on permanents:** these use the same effect list as spells.

  | Trigger | Example |
  |---|---|
  | When this creature enters, ... | Mulldrifter: "When Mulldrifter enters, draw two cards." |
  | When this creature dies, ... | |
  | Whenever this creature attacks, ... | |
  | Whenever this creature deals combat damage to a player, ... | |
  | At the beginning of your upkeep / end step, ... | |

  - Triggers go on the stack the next time a player would get priority. The active player's go
    first, so they resolve last, and players can respond to them.
  - Targets are chosen when a trigger goes on the stack. A trigger with no legal target is removed.
  - "You may" abilities ask their controller when they resolve.
  - A card can call itself by its full name, its short legendary name ("Omnath"),
    "this creature", or "it".
  - A trigger whose effect isn't understood is ignored.
- **Other rules text on permanents:** besides triggers and mana abilities, rules text on permanents
  (static abilities, activated abilities) isn't implemented yet.

- **Hidden cards:** a drawn card's name goes only to the player who drew it.
- **Replays:** the same `seed` gives the same shuffles.

## Bots and goldfishing

```python
from infernal_machine.bot import BotPlayer, goldfish

game = Game([(BotPlayer("Bot", deck), deck), (tcp_player, other_deck)])
stats = goldfish(deck, games=5000, turns=5)
# GoldfishStats(mulligan_rate=0.188, average_opening_lands=3.01,
#               land_drop_rate={1: 1.0, 2: 0.998, 3: 0.918, 4: 0.772, 5: 0.596})
```

- **`BotPlayer`:** keeps hands with 2-5 lands, and keeps anything after two mulligans.
  It plays a land whenever it can, then casts its commander if it can,
  then its most expensive affordable spell, and otherwise passes.
  It targets opponents' things when it can, never responds to its own spell,
  and always returns its commander to the command zone. In combat it attacks the opponent
  with the lowest life with every creature that has power. It blocks when its blocker survives,
  and chump-blocks the biggest attacker once it's at 10 life or less. When bottoming or discarding,
  it drops a land if over half the hand is lands, otherwise its most expensive spell.
- **`goldfish`:** plays the deck alone many times with the same mulligan rules and one land a turn.
  It reports how often you mulligan, how many lands the kept hand has, and how often
  you've made every land drop through each turn. The example above is a 38-land deck.

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
