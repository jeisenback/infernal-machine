"""Host a Commander table: human players join over TCP and bots fill the other seats.

    python -m infernal_machine.server --humans 2 --bots 2 --bot-deck deck.txt

Each human sends their decklist in the hello message (see tcp.py; `python -m infernal_machine.client`
does this). The server fetches the cards, checks the deck against the Commander rules, and either
seats the player or tells them why not. If a human disconnects mid-game, a bot takes over their seat until they
connect again with the same name: the server keeps listening during the game, and a hello with a seated player's name
gives them their seat back (a deck isn't needed, and a connection still open under that name is dropped).
"""

from __future__ import annotations

import argparse
import socket
import sys
import threading
from pathlib import Path
from typing import Callable, Sequence

from .bot import BotPlayer
from .cards import BulkSource, CachedSource, CardNotFound, CardSource, Deck, ScryfallSource, load_deck
from .commander import deck_problems
from .game import Game
from .tcp import Disconnected, TcpPlayer, listen

MAX_PROBLEMS_SHOWN = 10


class DeckRejected(Exception):
    """A deck the table can't use; the message is what the player is told."""


class AutoPilotPlayer:
    """A human's seat. If their connection drops, a bot (which has watched the whole game) plays on until the human
    connects again (`reconnect`, called from another thread: the game thread reads `_human` once per call, so a swap
    lands between calls, and closing the old connection wakes a read blocked on it)."""

    wants_state = True

    def __init__(self, human: TcpPlayer, bot: BotPlayer, seat: int = 0):
        self.name = human.name
        self.seat = seat
        self._human: TcpPlayer | None = human
        self._bot = bot
        self._introductions: list[dict] = []  # the "seat" events, which a rejoining client needs to name everyone

    @property
    def disconnected(self) -> bool:
        return self._human is None

    def notify(self, event: dict) -> None:
        if event.get("event") == "seat":
            self._introductions.append(event)
        self._bot.notify(event)
        human = self._human
        if human is not None:
            try:
                human.notify(event)
            except Disconnected:
                self._drop(human)

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        human = self._human
        if human is not None:
            try:
                return human.choose(prompt, options)
            except Disconnected:
                self._drop(human)
        return self._bot.choose(prompt, options)

    def reconnect(self, human: TcpPlayer) -> None:
        """A new connection for this seat takes over; one still open is closed (it may be dead without the server
        knowing). The newcomer is welcomed and told who sits where; the board comes with their next decision."""
        old, self._human = self._human, human
        if old is not None:
            old.close()
        human.welcome(self.seat, rejoined=True)
        for event in self._introductions:
            human.notify(event)

    def _drop(self, human: TcpPlayer) -> None:
        human.close()
        if self._human is human:
            self._human = None


def _reject_message(problems: list[str]) -> str:
    shown = problems[:MAX_PROBLEMS_SHOWN]
    more = len(problems) - len(shown)
    return "Your deck was rejected:\n" + "\n".join(f"- {p}" for p in shown) + (f"\n- and {more} more" if more else "")


def load_human_deck(hello: dict, source: CardSource, check: bool) -> Deck:
    text = hello.get("deck")
    if not isinstance(text, str) or not text.strip():
        raise DeckRejected(_reject_message(['Send your decklist in the hello message ("deck").']))
    try:
        deck = load_deck(text, source)
    except (CardNotFound, ValueError, OSError) as err:
        raise DeckRejected(_reject_message([f"Couldn't read your deck: {err}"])) from err
    if check and (problems := deck_problems(deck)):
        raise DeckRejected(_reject_message(problems))
    return deck


def seat_humans(server: socket.socket, count: int, source: CardSource, check: bool, taken_names: set[str],
                log: Callable[[str], None] = print, handshake_timeout: float = 10.0) -> list[tuple[TcpPlayer, Deck]]:
    """Accept connections until `count` players with usable decks and unused names are seated.
    Anyone else is told why and dropped, and their place stays open."""
    seated: list[tuple[TcpPlayer, Deck]] = []
    names = set(taken_names)
    while len(seated) < count:
        conn, _ = server.accept()
        conn.settimeout(handshake_timeout)
        player = TcpPlayer(conn)
        try:
            hello = player.read_hello()
            name = hello["name"].strip()
            if not name or name in names:
                player.send_error(f"The name {name!r} is empty or already taken; pick another.")
                raise Disconnected("bad name")
            deck = load_human_deck(hello, source, check)
            player.name = name
            player.welcome(len(seated))
            conn.settimeout(None)
        except DeckRejected as err:
            log(f"{player.name}: deck rejected")
            try:
                player.send_error(str(err))
            except Disconnected:
                pass
            player.close()
            continue
        except Disconnected:
            player.close()
            continue
        names.add(name)
        seated.append((player, deck))
        log(f"{name} joined ({len(seated)}/{count})")
        for other, _ in seated:
            try:
                other.notify({"event": "lobby", "joined": [p.name for p, _ in seated], "humans": count})
            except Disconnected:
                pass
    return seated


def rejoin_players(server: socket.socket, pilots: dict[str, AutoPilotPlayer], over: threading.Event,
                   log: Callable[[str], None] = print, handshake_timeout: float = 10.0) -> None:
    """Keep accepting connections during the game: a hello with a seated player's name gives them their seat back
    (`AutoPilotPlayer.reconnect`); anyone else is told the game has started. Ends when `over` is set or the
    listening socket is closed."""
    while not over.is_set():
        try:
            conn, _ = server.accept()
        except TimeoutError:
            continue
        except OSError:
            return
        conn.settimeout(handshake_timeout)
        player = TcpPlayer(conn)
        try:
            name = player.read_hello()["name"].strip()
            pilot = pilots.get(name)
            if pilot is None or over.is_set():
                player.send_error(f"The game has started and {name!r} isn't playing in it.")
                raise Disconnected("not a player")
            conn.settimeout(None)
            pilot.reconnect(player)
            log(f"{name} rejoined")
        except Disconnected:
            player.close()


def run_table(server: socket.socket, humans: int, bot_decks: list[str], source: CardSource, seed: int | None = None,
              check_decks: bool = True, max_turns: int = 300, log: Callable[[str], None] = print,
              handshake_timeout: float = 10.0) -> str | None:
    """Wait for `humans` players on `server`, add one bot per entry of `bot_decks` (decklist texts), play the
    game, and return the winner's name (None if nobody won within `max_turns`). While the game runs, a player who
    dropped can connect again and take their seat back."""
    if humans + len(bot_decks) < 2:
        raise ValueError("A table needs at least two players")
    bots: list[tuple[str, Deck]] = []
    for n, text in enumerate(bot_decks, 1):
        deck = load_deck(text, source)
        if check_decks and (problems := deck_problems(deck)):
            raise ValueError(f"Bot deck {n} isn't legal: {'; '.join(problems[:MAX_PROBLEMS_SHOWN])}")
        bots.append((f"Bot {n}", deck))

    log(f"Waiting for {humans} player(s); {len(bots)} bot(s) will fill the other seats.")
    seated = seat_humans(server, humans, source, check_decks, {name for name, _ in bots}, log, handshake_timeout)
    over = threading.Event()
    pilots = [AutoPilotPlayer(human, BotPlayer(human.name, deck), seat) for seat, (human, deck) in enumerate(seated)]
    try:
        players = [(pilot, deck) for pilot, (_, deck) in zip(pilots, seated)]
        players += [(BotPlayer(name, deck), deck) for name, deck in bots]
        threading.Thread(target=rejoin_players, args=(server, {p.name: p for p in pilots}, over, log, handshake_timeout),
                         daemon=True).start()
        log("Starting the game.")
        winner = Game(players, seed=seed).play(max_turns=max_turns)
        log(f"Game over: {winner.name} wins." if winner else f"Game over: no winner after {max_turns} turns.")
        return winner.name if winner else None
    finally:
        over.set()
        for pilot in pilots:
            if pilot._human is not None:
                pilot._human.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m infernal_machine.server", description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--humans", type=int, default=1, help="how many players will connect")
    parser.add_argument("--bots", type=int, default=3, help="how many bots fill the other seats")
    parser.add_argument("--bot-deck", action="append", default=[], metavar="FILE",
                        help="a decklist for the bots; repeat for several (bots take them in turn)")
    parser.add_argument("--seed", type=int, help="make shuffles repeatable")
    parser.add_argument("--max-turns", type=int, default=300)
    parser.add_argument("--cache", default=".cache/cards.json", help="where fetched cards are saved")
    parser.add_argument("--bulk", metavar="FILE", help="look cards up in Scryfall's bulk Oracle Cards data, "
                        "downloaded to FILE and refreshed weekly, instead of calling the API per card")
    parser.add_argument("--no-check", action="store_true", help="don't require decks to be legal Commander decks")
    args = parser.parse_args(argv)
    if args.bots and not args.bot_deck:
        parser.error("--bot-deck is needed when there are bots")
    if args.humans + args.bots < 2:
        parser.error("a table needs at least two players")

    bot_texts = [Path(p).read_text() for p in args.bot_deck]
    bot_decks = [bot_texts[i % len(bot_texts)] for i in range(args.bots)]
    source = BulkSource(args.bulk) if args.bulk else CachedSource(ScryfallSource(), args.cache)
    server = listen(args.host, args.port)
    print(f"Listening on {args.host}:{server.getsockname()[1]}")
    try:
        run_table(server, args.humans, bot_decks, source, args.seed, not args.no_check, args.max_turns)
    except (ValueError, CardNotFound, OSError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped.")
    finally:
        server.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
