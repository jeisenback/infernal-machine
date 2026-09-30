"""Terminal client for a game server.

    python -m infernal_machine.client --host localhost --port 4000 --name Alice --deck deck.txt

It prints what happens as plain sentences, shows the board when it's your turn to decide, and asks you to
pick numbered options. At a priority prompt, pressing Enter passes; type b to see the board again.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from collections import Counter
from typing import Callable

from .tcp import send_promptly

BOARD_KEY = "b"


def _permanent_text(p: dict) -> str:
    text = p["name"]
    if p["power"] is not None:
        text += f" {p['power']}/{p['toughness']}"
    tags = []
    if p["tapped"]:
        tags.append("tapped")
    if p["sick"]:
        tags.append("summoning sick")
    if p["damage"]:
        tags.append(f"{p['damage']} damage")
    if p["loyalty"] is not None:
        tags.append(f"loyalty {p['loyalty']}")
    tags += [f"{count} {kind} counter{'s' if count != 1 else ''}" for kind, count in p["counters"].items()]
    if p["attached_to"]:
        tags.append(f"on {p['attached_to']}")
    if p["token"]:
        tags.append("token")
    return text + (f" [{', '.join(tags)}]" if tags else "")


def _grouped(texts: list[str]) -> str:
    return ", ".join(f"{text} x{n}" if n > 1 else text for text, n in Counter(texts).items())


def render_board(state: dict) -> str:
    """The board from a "state" event as text."""
    me = state["you"]
    names = {s["seat"]: s["name"] for s in state["seats"]}
    lines = [f"=== Turn {state['turn']}, {state['step']}, {names[state['active']]}'s turn ==="]
    if state["stack"]:
        lines.append("Stack (top first): " + ", ".join(
            f"{i['ability'] or i['card']} ({names[i['seat']]})" for i in reversed(state["stack"])))
    for seat in state["seats"]:
        you = " (you)" if seat["seat"] == me else ""
        lost = " - ELIMINATED" if seat["lost"] else ""
        lines.append(f"{seat['name']}{you}: life {seat['life']} | hand {seat['hand']} | library {seat['library']} "
                     f"| graveyard {len(seat['graveyard'])} | exile {len(seat['exile'])}{lost}")
        if seat["command_zone"]:
            lines.append("  Command zone: " + ", ".join(
                f"{c['name']} (tax {c['tax']})" if c["tax"] else c["name"] for c in seat["command_zone"]))
        if seat["commander_damage"]:
            lines.append("  Commander damage taken: " + ", ".join(
                f"{d['damage']} from {names[d['from_seat']]}'s {d['commander']}" for d in seat["commander_damage"]))
        lands = [_permanent_text(p) for p in seat["battlefield"] if "Land" in p["type"]]
        others = [_permanent_text(p) for p in seat["battlefield"] if "Land" not in p["type"]]
        lines.append("  Lands: " + (_grouped(lands) if lands else "none"))
        lines.append("  Permanents: " + (_grouped(others) if others else "none"))
        if seat["graveyard"]:
            lines.append("  Graveyard: " + ", ".join(seat["graveyard"][-8:]) + (" ..." if len(seat["graveyard"]) > 8 else ""))
    lines.append("Your hand: " + (", ".join(f"{n}. {c}" for n, c in enumerate(state["hand"], 1)) or "empty"))
    return "\n".join(lines)


class Narrator:
    """Turns game events into sentences."""

    def __init__(self) -> None:
        self.names: dict[int, str] = {}
        self.me: int | None = None

    def who(self, seat: int) -> str:
        return "You" if seat == self.me else self.names.get(seat, f"Seat {seat}")

    def verb(self, seat: int, base: str, third: str | None = None) -> str:
        """"play" for you, "plays" for everyone else (or `third`, like "has" / "scries")."""
        return base if seat == self.me else (third or base + "s")

    def poss(self, seat: int) -> str:
        return "your" if seat == self.me else f"{self.names.get(seat, f'Seat {seat}')}'s"

    def narrate(self, e: dict) -> str | None:
        kind, card = e["event"], e.get("card", "")
        seat = e.get("seat")
        who = self.who(seat) if seat is not None else ""
        v = (lambda base, third=None: self.verb(seat, base, third)) if seat is not None else None
        targets = f" targeting {', '.join(e['targets'])}" if e.get("targets") else ""
        ability = (e.get("ability") or "").rstrip(".")  # sentences below add their own period
        if kind == "seat":
            self.names[seat] = e["name"]
            commanders = ", ".join(e["commanders"])
            return f"Seat {seat}: {e['name']}" + (f" (commander: {commanders})" if commanders else "")
        if kind == "lobby":
            return f"Players joined: {', '.join(e['joined'])} ({len(e['joined'])}/{e['humans']})"
        if kind == "starting_player":
            return f"{who} {v('go', 'goes')} first."
        if kind == "opening_hand":
            return f"Your hand ({e['mulligans']} mulligans): " + ", ".join(e["cards"])
        if kind == "kept":
            return f"{who} {v('keep')} {e['hand_size']} cards."
        if kind == "turn":
            return f"\n--- Turn {e['turn']}: {self.poss(seat)} turn ---"
        if kind == "draw":
            return f"You draw {card}."
        if kind in ("drew", "state"):
            return None
        if kind == "play_land":
            return f"{who} {v('play')} {card}."
        if kind in ("destroyed", "died", "unattached"):
            return f"{card} ({who}) is {'destroyed' if kind == 'destroyed' else 'put into the graveyard'}."
        if kind == "exiled":
            return f"{card} ({who}) is exiled."
        if kind == "sacrificed":
            return f"{who} {v('sacrifice')} {card}."
        if kind == "returned":
            return f"{card} ({who}) returns to its owner's hand."
        if kind == "cast":
            origin = " from the command zone" if e.get("from") == "command_zone" else ""
            x = f" with X={e['x']}" if e.get("x") else ""
            return f"{who} {v('cast', 'casts')} {card}{origin}{x}{targets}."
        if kind == "activate":
            return f"{who} {v('activate')} {card}: {ability}{targets}."
        if kind == "trigger":
            return f"{card} triggers for {who}: {ability}{targets}."
        if kind == "resolve":
            if e.get("declined"):
                return f"{card}: {who} {v('decline')} the optional ability."
            note = " (its effect isn't implemented)" if e.get("unsupported") else ""
            return f"{card}'s ability resolves{note}." if ability else f"{card} resolves{note}."
        if kind == "fizzle":
            return f"{card}'s ability fizzles: its target is gone." if ability else f"{card} fizzles: its target is gone."
        if kind == "countered":
            return f"{card}'s ability is countered." if ability else f"{card} is countered."
        if kind == "damage_prevented":
            return f"Damage to {card} is prevented (protection)."
        if kind == "ward_paid":
            return f"{who} {v('pay')} the ward cost {e['cost']}."
        if kind == "life":
            return f"{who} {v('gain') if e['change'] > 0 else v('lose')} {abs(e['change'])} life ({e['life']})."
        if kind == "damage":
            return f"{card} is dealt {e['amount']} damage."
        if kind == "commander_damage":
            return (f"{who} {v('have', 'has')} taken {e['total']} damage from "
                    f"{self.poss(e['from_seat'])} {e['commander']}.")
        if kind == "attack":
            return f"{who} {v('attack')} {self.who(e['defender'])} with {card}."
        if kind == "block":
            return f"{who} {v('block')} {e['attacker']} with {card}."
        if kind == "block_removed":
            return f"{card} can't block alone ({e['reason']})."
        if kind == "token_created":
            size = f"{e['power']}/{e['toughness']} " if e.get("power") else ""
            return f"{who} {v('create')} a {size}{card} token."
        if kind == "counters":
            return f"{card} gets {e['added']} {e['counter']} counter(s) ({e['total']})."
        if kind == "modified":
            gained = f" and {', '.join(e['keywords'])}" if e["keywords"] else ""
            return f"{card} gets {e['power']:+d}/{e['toughness']:+d}{gained} until end of turn."
        if kind == "attached":
            return f"{card} is attached to {e['to']}."
        if kind == "to_command_zone":
            return f"{card} goes to the command zone."
        if kind == "put_onto_battlefield":
            return f"{card} enters the battlefield{' tapped' if e.get('tapped') else ''} for {who}."
        if kind == "left_graveyard":
            return f"{card} leaves {self.poss(seat)} graveyard for the {e['to']}."
        if kind == "graveyard_exiled":
            return f"{self.poss(seat).capitalize()} graveyard is exiled."
        if kind == "discard":
            return f"{who} {v('discard')} {card}."
        if kind == "searched":
            if not e.get("found"):
                return f"{who} {v('search', 'searches')} their library and {v('find', 'finds')} nothing."
            return f"{who} {v('search', 'searches')} their library" + (f": {e['card']}." if e.get("card") else ".")
        if kind == "revealed":
            return f"{who} {v('reveal')} {card}."
        if kind == "scry":
            bottom = f" (bottomed: {', '.join(e['bottom'])})" if e.get("bottom") else ""
            return f"{who} {v('scry', 'scries')} {e['count']}{bottom}."
        if kind == "surveil":
            binned = f" ({', '.join(e['graveyard'])} to the graveyard)" if e["graveyard"] else ""
            return f"{who} {v('surveil')} {e['count']}{binned}."
        if kind == "milled":
            return f"{who} {v('mill')} {', '.join(e['cards']) or 'nothing'}."
        if kind == "player_lost":
            return f"{who} {v('have', 'has')} lost the game ({e['reason'].replace('_', ' ')})."
        if kind == "game_over":
            if e["winner"] is None:
                return f"\n=== Game over: nobody wins (turn {e['turn']}) ==="
            winner = self.who(e["winner"])
            return f"\n=== Game over: {winner} {self.verb(e['winner'], 'win')} (turn {e['turn']}) ==="
        return json.dumps(e, separators=(",", ":"))


class Client:
    def __init__(self, sock: socket.socket, name: str, deck_text: str | None = None,
                 ask: Callable[[str], str] = input, show: Callable[[str], None] = print, auto_pass: bool = True):
        self.sock = sock
        send_promptly(sock)
        self.name = name
        self.deck_text = deck_text
        self.ask = ask
        self.show = show
        self.auto_pass = auto_pass  # answer prompts whose only option is Pass without asking
        self.narrator = Narrator()
        self.state: dict | None = None
        self._last_board = ""
        self._reader = sock.makefile("r", encoding="utf-8", newline="\n")

    def run(self) -> None:
        """Play until the server closes the connection or the player's input ends."""
        hello = {"type": "hello", "name": self.name}
        if self.deck_text:
            hello["deck"] = self.deck_text
        self._send(hello)
        try:
            for line in self._reader:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                kind = message.get("type")
                if kind == "welcome":
                    self.narrator.me = message["seat"]
                    self.show(f"Joined the table at seat {message['seat']}.")
                elif kind == "error":
                    self.show(f"Server: {message['message']}")
                elif kind == "event":
                    self._event(message)
                elif kind == "choose":
                    self._choose(message)
        except (EOFError, KeyboardInterrupt):
            self.show("\nLeft the game; a bot will play your seat.")
        finally:
            self._reader.close()
            self.sock.close()

    def _send(self, message: dict) -> None:
        self.sock.sendall((json.dumps(message) + "\n").encode("utf-8"))

    def _event(self, message: dict) -> None:
        event = {k: v for k, v in message.items() if k != "type"}
        if event["event"] == "state":
            self.state = event
            return
        text = self.narrator.narrate(event)
        if text:
            self.show(text)

    def _show_board(self, only_if_changed: bool) -> None:
        if self.state is None:
            return
        board = render_board(self.state)
        if not only_if_changed or board != self._last_board:
            self.show("\n" + board)
            self._last_board = board

    def _choose(self, message: dict) -> None:
        prompt, options = message["prompt"], message["options"]
        if self.auto_pass and options == ["Pass"]:
            self._send({"type": "response", "id": message["id"], "choice": 0})
            return
        if prompt.startswith("Priority"):
            self._show_board(only_if_changed=True)
        self.show(f"\n{prompt}")
        for n, option in enumerate(options, 1):
            self.show(f"  {n}. {option}")
        default = options.index("Pass") + 1 if "Pass" in options else None
        hint = f"1-{len(options)}" + (", Enter passes" if default else "") + f", {BOARD_KEY} shows the board"
        while True:
            answer = self.ask(f"[{hint}] > ").strip().lower()
            if answer in (BOARD_KEY, "board"):
                self._show_board(only_if_changed=False)
            elif not answer and default:
                choice = default
                break
            elif answer.isdigit() and 1 <= int(answer) <= len(options):
                choice = int(answer)
                break
            else:
                self.show(f"Enter a number from 1 to {len(options)}.")
        self._send({"type": "response", "id": message["id"], "choice": choice - 1})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m infernal_machine.client", description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--name", required=True)
    parser.add_argument("--deck", required=True, metavar="FILE", help="your decklist (Commander / Deck sections)")
    args = parser.parse_args(argv)
    with open(args.deck) as f:
        deck_text = f.read()
    try:
        sock = socket.create_connection((args.host, args.port))
    except OSError as err:
        print(f"Couldn't connect to {args.host}:{args.port}: {err}", file=sys.stderr)
        return 1
    Client(sock, args.name, deck_text).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
