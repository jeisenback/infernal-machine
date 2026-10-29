# Playing over TCP

Hosting a table, joining it, and the protocol between them.

## Playing over TCP

**Server** (`python -m infernal_machine.server`) hosts one table:

| Option | Meaning |
|---|---|
| `--humans N` (default 1) | how many players will connect |
| `--bots N` (default 3) | bots that fill the other seats |
| `--bot-deck FILE` | decklist for the bots; repeat the option to give different bots different decks |
| `--port`, `--host` | where to listen (default `0.0.0.0:4000`) |
| `--seed N` | repeat the same shuffles |
| `--max-turns N` (default 300) | end the game with no winner after this many turns |
| `--timer SECONDS` | a clock on every decision: when it runs out, a bot answers for the player (default: no limit) |
| `--password TEXT` | players and spectators must give it to join (see below) |
| `--cache FILE` | where fetched cards are saved (default `.cache/cards.json`) |
| `--format NAME` (default `commander`) | the game to play, any format in `formats.FORMATS` (Commander, Standard, Pioneer, Modern, Legacy, Vintage, Pauper, Brawl, Duel Commander, Oathbreaker); decks are checked against it |
| `--no-check` | accept decks that aren't legal for the format |
| `--allow NAME` | house rules: accept this card although the format doesn't allow it (repeat, or a comma list); every other deck rule still holds |
| `--allow-banned` | house rules: accept any card the format bans (not one outside its pool, such as a silver-border card) |

Each human sends their decklist when they connect. The server fetches the cards, checks the deck, and either
seats the player or explains why not (wrong size, a card outside the commander's colors, an unknown card, a name
already in use), leaving the seat open. If a human disconnects during the game, a bot takes over their seat until
they come back: the server keeps listening, and connecting again with the same name (no deck needed) gives them
their seat back. The welcome says `rejoined`, the seats are introduced again, and the board arrives with their next
decision. A connection still open under that name is dropped, since it may be dead without the server knowing; there
is no password yet, so anyone who knows a player's name can take their seat. Someone else is told the game has started.

**Password.** With `--password`, every hello (a player's, a rejoin, a spectator's) must carry `"password"`; otherwise
the connection gets `Wrong password.` and is dropped, and a seat stays open. This also stops someone who only knows a
player's name from taking their seat on a rejoin. The password is sent as plain text over an unencrypted connection, so it
keeps out the curious, not someone who can read the network traffic.

**Spectators.** A hello with `"spectate": true` (no deck needed; `--name` is optional on the clients) watches the game
instead of playing: the welcome is `{"type": "welcome", "spectator": true}`, and from then on they are sent every public
event and the board (`state`, with `"you": -1` and an empty `hand`) whenever it changes. They can join in the lobby or
during the game (they are told who sits where and the current board first), and are never sent a hand, a card drawn
privately, an opening hand or what a scry or a search found. They are never asked to choose anything.

With `--timer`, each decision is sent with its time limit (`"seconds"` in the `choose` message). A player who hasn't
answered by then gets a `timed_out` event saying what the bot chose for them, and keeps their seat for the next
decision; the terminal client shows the limit in the prompt's hint and the browser client counts it down. An answer
that arrives late is refused, like any answer to a question that is no longer open.

**Client** (`python -m infernal_machine.client --name Alice --deck deck.txt [--host H] [--port P]`):
- Events are printed as sentences ("Bot 1 casts Sol Ring.", "You lose 3 life (25).").
- When you have a decision, the board is shown and the options are numbered. Type a number.
  At a priority prompt, Enter passes. Type `b` to show the board again.
- `--spectate` (no `--name` or `--deck` needed) watches a table instead: the events are printed, and the board comes
  with each turn.
- `--password TEXT` joins a table that has one.
- Prompts where passing is your only option are answered for you.
- Your hand is shown to you only. Opponents' hands and libraries appear as counts.
- On a table with `--timer`, the hint shows the seconds you have; when they run out a bot answers and you are told
  what it chose.

**Browser client** (`python -m infernal_machine.web --name Alice --deck deck.txt [--host H] [--port P] [--listen 8765] [--no-browser]`):
- Joins the table like the terminal client, then serves a page at `http://127.0.0.1:8765/` (`--listen` picks the
  port) and opens it in your browser (`--no-browser` just prints the address). Nothing beyond the standard library.
- The page shows each seat's life, hand and library counts, graveyard and exile (hover for the cards), command zone
  and commander damage, the permanents as cards (tapped ones tilt, summoning-sick ones are marked, with counters,
  damage and attachments) and the lands as counted chips; the stack; your hand; the log of events as sentences.
  Your seat is at the bottom. It follows your light or dark theme and fits a phone.
- A decision shows its prompt with one button per option (Pass stands out) and, on a table with `--timer`, a
  countdown. The page asks the client for changes
  (`GET /state?since=N`, answered when something changed) and answers with `POST /choose` (`{"id", "choice"}`).
- Prompts where passing is your only option are answered for you, as in the terminal client.
- Dropping and reconnecting works the same way: run it again with the same name.
- `--spectate` and `--password` work as in the terminal client; a spectator's page shows the board and the log with
  no hand and no buttons.

All three can also be run as `infernal-server`, `infernal-client` and `infernal-web` after `pip install .`.

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
| client -> server | `{"type": "hello", "name": "Alice", "deck": "<decklist text>"}` (must come first; the deck is optional, but the game server needs it) |
| server -> client | `{"type": "welcome", "seat": 0}` (`"rejoined": true` when a dropped player took their seat back) |
| server -> client | `{"type": "event", ...}` (no reply) |
| server -> client | `{"type": "event", "event": "state", ...}`: the whole board, sent before each of your decisions. It has `turn`, `step`, `active`, `you`, your `hand`, the `stack`, and for each seat its life, hand and library counts, graveyard, exile, command zone (with commander tax), commander damage, and battlefield (with current power and toughness, counters and attachments) |
| server -> client | `{"type": "choose", "id": 1, "prompt": "...", "options": ["Keep", "Mulligan"]}` (`"seconds": 60` when the table has a timer; `"kind"` and `"subject"` too when the question is a typed prompt, e.g. `"kind": "priority", "subject": "main1"`: match on the kind, not on the wording) |
| server -> client | `{"type": "event", "event": "timed_out", "prompt": "...", "choice": "Pass"}`: the clock ran out and a bot chose for you |
| client -> server | `{"type": "response", "id": 1, "choice": 0}` |
| server -> client | `{"type": "error", "message": "..."}` (after bad input the prompt is sent again) |

You can connect by hand with `nc localhost 4000`.
