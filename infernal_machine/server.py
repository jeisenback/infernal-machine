"""Host a Commander table: human players join over TCP and bots fill the other seats.

    python -m infernal_machine.server --humans 2 --bots 2 --bot-deck deck.txt

Each human sends their decklist in the hello message (see tcp.py; `python -m infernal_machine.client`
does this). The server fetches the cards, checks the deck against the Commander rules, and either
seats the player or tells them why not. If a human disconnects mid-game, a bot takes over their seat.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path
from typing import Callable, Sequence

from .bot import BotPlayer
from .cards import CachedSource, CardNotFound, CardSource, Deck, ScryfallSource, load_deck
from .commander import deck_problems
from .game import Game
from .tcp import Disconnected, TcpPlayer, listen

MAX_PROBLEMS_SHOWN = 10


class DeckRejected(Exception):
    """A deck the table can't use; the message is what the player is told."""


class AutoPilotPlayer:
    """A human's seat. If their connection drops, a bot (which has watched the whole game) plays on."""

    wants_state = True

    def __init__(self, human: TcpPlayer, bot: BotPlayer):
        self.name = human.name
        self._human = human
        self._bot = bot
        self.disconnected = False

    def notify(self, event: dict) -> None:
        self._bot.notify(event)
        if not self.disconnected:
            try:
                self._human.notify(event)
            except Disconnected:
                self.disconnected = True

    def choose(self, prompt: str, options: Sequence[str]) -> int:
        if not self.disconnected:
            try:
                return self._human.choose(prompt, options)
            except Disconnected:
                self.disconnected = True
        return self._bot.choose(prompt, options)


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


def run_table(server: socket.socket, humans: int, bot_decks: list[str], source: CardSource, seed: int | None = None,
              check_decks: bool = True, max_turns: int = 300, log: Callable[[str], None] = print,
              handshake_timeout: float = 10.0) -> str | None:
    """Wait for `humans` players on `server`, add one bot per entry of `bot_decks` (decklist texts), play the
    game, and return the winner's name (None if nobody won within `max_turns`)."""
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
    try:
        players = [(AutoPilotPlayer(human, BotPlayer(human.name, deck)), deck) for human, deck in seated]
        players += [(BotPlayer(name, deck), deck) for name, deck in bots]
        log("Starting the game.")
        winner = Game(players, seed=seed).play(max_turns=max_turns)
        log(f"Game over: {winner.name} wins." if winner else f"Game over: no winner after {max_turns} turns.")
        return winner.name if winner else None
    finally:
        for human, _ in seated:
            human.close()


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
    parser.add_argument("--no-check", action="store_true", help="don't require decks to be legal Commander decks")
    args = parser.parse_args(argv)
    if args.bots and not args.bot_deck:
        parser.error("--bot-deck is needed when there are bots")
    if args.humans + args.bots < 2:
        parser.error("a table needs at least two players")

    bot_texts = [Path(p).read_text() for p in args.bot_deck]
    bot_decks = [bot_texts[i % len(bot_texts)] for i in range(args.bots)]
    source = CachedSource(ScryfallSource(), args.cache)
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
