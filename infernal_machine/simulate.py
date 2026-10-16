"""Goldfish simulation: play a deck alone and measure how its mana and curve behave.

    python -m infernal_machine.simulate DECKLIST [--games N] [--turns N] [--seed N] [--play]

Each game uses the bot's mulligan rules, draws a card a turn, plays one land a turn, and casts whatever it can pay for
(color by color, through `mana.pay`). It models mana and bodies only, not rules text: a spell is cast when its mana
cost can be paid, and nothing else it does is simulated except that creatures attack for their power from the turn
after they enter (or at once with haste). Mana rocks and mana creatures count as sources. Conditional "enters tapped"
lands and shocklands are treated as untapped, a land that fetches a basic land (Fabled Passage, Evolving Wilds) brings the
basic the hand needs, X is 0, and a commander is cast from the command zone with its tax ({2} for each earlier cast), so the
numbers are for comparing builds, not for predicting a game. `--commander-dies N` sends every commander on the battlefield back
to the command zone at the start of turn N, as if removed, so the report shows how soon the recast comes and how much the tax
costs a deck that leans on its commander. Eminence cost reducers and the rest of a commander's text are not modeled. Works for any
format: pass a 60-card list for Standard. `goldfish.py` plays the same deck through the real engine, with every card's text, and
reports in this module's shape so the two can be set side by side.
"""

from __future__ import annotations

import dataclasses
import io
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .analysis import is_land
from .bot import opening_hand
from .cards import Card, Deck
from .mana import Cost, pay, parse_cost

_NUMBER = {"one": 1, "two": 2, "three": 3}
_TAP_FOR_SYMBOLS = re.compile(r"\{T\}: Add ((?:\{[WUBRGC]\})+)")
_TAP_FOR_COUNT = re.compile(r"\{T\}: Add (one|two|three) mana")
_TAP_FOR_ANY = re.compile(r"\{T\}: Add ")


@dataclass
class CardStats:
    name: str
    copies: int
    seen_rate: float  # share of games in which it was in hand (or the command zone) by the last turn
    cast_rate: float  # share of games in which it was cast by the last turn
    cast_when_seen: float  # of the games where it was seen, the share where it was cast
    average_cast_turn: float | None  # first turn cast, over the games where it was cast
    average_wait: float | None  # turns between seeing it and casting it, over the games where it was cast
    on_curve: float | None = None  # of the games where it could be cast by the last turn, the share where it was, on the turn its mana value allowed (or the turn it was seen, if later)
    average_casts: float = 0.0  # times cast per game (a commander is cast again after it goes back to the command zone)
    recast_rate: float = 0.0  # share of games in which it was cast a second time
    average_recast_turn: float | None = None  # the turn of that second cast, over the games where it happened


@dataclass
class SimStats:
    games: int
    turns: int
    mulligan_rate: float
    average_opening_lands: float
    land_drop_rate: dict[int, float]  # turn -> share of games with a land played on every turn so far
    mana_available: dict[int, float]  # turn -> average mana from sources that could be tapped
    mana_spent: dict[int, float]  # turn -> average mana spent on spells
    stuck_on_colors: dict[int, float]  # turn -> share of games holding a spell the lands' count could pay for but their colors could not
    damage: dict[int, float]  # turn -> average total combat damage dealt so far (all unblocked, no removal)
    cards: list[CardStats] = field(default_factory=list)
    drawn: dict[int, float] = field(default_factory=dict)  # turn -> average cards drawn so far (only the engine goldfish knows)
    permanents: dict[int, float] = field(default_factory=dict)  # turn -> average permanents on the battlefield at its end (engine goldfish)
    dropped: int = 0  # games the engine goldfish could not finish (an error or a time limit), left out of every number

    @property
    def on_curve(self) -> float | None:
        """The spells drawn that were cast as soon as their mana value allowed, averaged over every copy in the deck."""
        rated = [(c.copies, c.on_curve) for c in self.cards if c.on_curve is not None]
        return round(sum(n * rate for n, rate in rated) / sum(n for n, _ in rated), 3) if rated else None

    @property
    def mana_efficiency(self) -> float:
        """Share of the available mana that was spent."""
        available = sum(self.mana_available.values())
        return round(sum(self.mana_spent.values()) / available, 3) if available else 0.0


@dataclass
class _Source:
    colors: frozenset[str]
    ready: int  # first turn it can be tapped


@dataclass
class _Body:
    power: int
    ready: int  # first turn it can attack


def _clean_lines(card: Card) -> list[str]:
    return [re.sub(r"\s*\([^)]*\)", "", line).strip() for line in card.oracle_text.splitlines()]


def enters_tapped(card: Card) -> bool:
    """Whether it always enters tapped (a conditional "unless ..." land is counted as untapped)."""
    pattern = re.compile(rf"(This [\w ]+?|{re.escape(card.name)}) enters( the battlefield)? tapped\.?")
    return any(pattern.fullmatch(line) for line in _clean_lines(card))


@dataclass(frozen=True)
class Fetch:
    """A land that is sacrificed for a basic land card: "{T}, Sacrifice this land: Search your library for a basic land card, put it
    onto the battlefield tapped, then shuffle." (Evolving Wilds), with Fabled Passage's "Then if you control four or more lands, untap
    that land." Played, it is taken to be cracked at once."""
    tapped: bool
    untap_at_four: bool


def fetch_land(card: Card) -> Fetch | None:
    """What a land that fetches a basic land is, or None. (A land that finds a Plains or an Island card by type is not read.)"""
    pattern = re.compile(rf"\{{T\}}(?:, Pay 1 life)?, Sacrifice (?:this land|{re.escape(card.name)}): Search your library for a basic land card, "
                         r"put it onto the battlefield( tapped)?, then shuffle\.( Then if you control four or more lands, untap that land\.)?")
    for line in _clean_lines(card):
        if m := pattern.fullmatch(line):
            return Fetch(bool(m[1]), bool(m[2]))
    return None


def land_colors(card: Card) -> frozenset[str]:
    return frozenset(card.produced_mana) or frozenset("C")


def mana_sources(card: Card) -> list[frozenset[str]]:
    """What a nonland permanent adds when tapped: one entry per mana. Empty if it makes no mana that way."""
    if is_land(card) or not any(kind in card.type_line for kind in ("Artifact", "Creature")):
        return []
    text = card.oracle_text
    if m := _TAP_FOR_SYMBOLS.search(text):
        return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1])]
    colors = frozenset(card.produced_mana) or frozenset("C")
    if m := _TAP_FOR_COUNT.search(text):
        return [colors] * _NUMBER[m[1]]
    return [colors] if _TAP_FOR_ANY.search(text) else []


def _power(card: Card) -> int:
    try:
        return max(0, int(card.power or 0))
    except ValueError:  # "*" and "1+*"
        return 0


def _cost(card: Card) -> Cost | None:
    cost = parse_cost(card.mana_cost)
    return cost.with_x(0) if cost is not None else None


def _plan(spells: list[Card], sources: list[frozenset[str]]) -> list[tuple[Card, int]]:
    """The spells to cast now with the mana they spend: mana makers first, then spells by cost. It tries the most
    expensive first and the cheapest first, and keeps whichever spends more mana (then casts more)."""
    best: list[tuple[Card, int]] = []
    for biggest_first in (True, False):
        order = sorted(spells, key=lambda c: (not mana_sources(c), -c.cmc if biggest_first else c.cmc))
        free = list(sources)
        plan = []
        for card in order:
            cost = _cost(card)
            if cost is None:
                continue
            used = pay(cost, free)
            if used is None:
                continue
            plan.append((card, len(used)))
            free = [s for i, s in enumerate(free) if i not in set(used)]
        if (sum(n for _, n in plan), len(plan)) > (sum(n for _, n in best), len(best)):
            best = plan
    return best


def _blocked_on_colors(hand: list[Card], sources: list[frozenset[str]]) -> bool:
    for card in hand:
        cost = _cost(card)
        if cost is not None and not is_land(card) and card.cmc <= len(sources) and pay(cost, sources) is None:
            return True
    return False


def _landing(land: Card, library: list[Card], wanted: set[str], sources: list[_Source], lands: int) -> tuple[frozenset[str], bool, Card | None]:
    """What playing `land` puts into play: (the colors it taps for, whether it enters tapped, the basic land it took from the library).
    A land that fetches takes the basic that adds a color the hand wants and the lands lack, and none if the library has no basic."""
    fetch = fetch_land(land)
    if fetch is None:
        return land_colors(land), enters_tapped(land), None
    have = {color for s in sources for color in s.colors}
    basics = {land_colors(c): c for c in library if is_land(c) and "Basic" in c.type_line}
    if not basics:
        return frozenset(), True, None
    colors = max(basics, key=lambda cs: (len(cs & wanted - have), len(cs & wanted), len(cs)))
    return colors, fetch.tapped and not (fetch.untap_at_four and lands + 1 >= 4), basics[colors]


COMMANDER_TAX = 2  # CR 903.8: {2} more for each time it has been cast from the command zone


def _taxed(card: Card, tax: int) -> Card:
    """The commander as it is cast now: its cost plus the tax, as a generic part of the mana cost."""
    return dataclasses.replace(card, mana_cost=f"{card.mana_cost}{{{tax}}}", cmc=card.cmc + tax) if tax else card


def _play_land(lands: list[Card], spells: list[Card], sources: list[_Source], turn: int, library: list[Card], in_play: int) -> Card | None:
    """The land to play: the one that lets the most mana be spent this turn, then the one that covers the most colors
    the hand's spells ask for, preferring an untapped land."""
    wanted = set(re.findall(r"[WUBRG]", "".join(c.mana_cost for c in spells)))
    best, best_key = None, None
    for land in {(land_colors(l), enters_tapped(l), fetch_land(l)): l for l in lands}.values():
        colors, tapped, _ = _landing(land, library, wanted, sources, in_play)
        now = [s.colors for s in sources if s.ready <= turn] + ([] if tapped or not colors else [colors])
        key = (sum(n for _, n in _plan(spells, now)), len(colors & wanted), not tapped, len(colors))
        if best_key is None or key > best_key:
            best, best_key = land, key
    return best


def _play(deck: Deck, turns: int, rng: random.Random, on_the_play: bool, free_mulligan: bool,
          commander_dies_on: int | None = None) -> dict:
    hand, library, mulligans = opening_hand(deck.main, rng, free_mulligan)
    command = list(deck.commanders)  # in the command zone now; a commander that is cast leaves it, and comes back if it dies
    commander_casts: Counter = Counter()
    commander_bodies: dict[str, tuple[_Body | None, list[_Source]]] = {}  # what a commander on the battlefield added
    recast_turn: dict[str, int] = {}
    sources: list[_Source] = []
    bodies: list[_Body] = []
    seen_turn: dict[str, int] = {c.name: 0 for c in hand + command if not is_land(c)}
    cast_turn: dict[str, int] = {}
    result = {"mulligans": mulligans, "opening_lands": sum(1 for c in hand if is_land(c)), "land_drops": [], "available": [],
              "spent": [], "stuck": [], "damage": [], "seen": seen_turn, "cast": cast_turn,
              "casts": commander_casts, "recast": recast_turn}
    missed = False
    total_damage = 0
    lands_in_play = 0
    for turn in range(1, turns + 1):
        if library and not (turn == 1 and on_the_play):
            card = library.pop(0)
            hand.append(card)
            if not is_land(card):
                seen_turn.setdefault(card.name, turn)
        if commander_dies_on == turn:  # removed on the way to this turn: back to the command zone, its body and mana gone
            for card in deck.commanders:
                if card.name in commander_bodies:
                    body, made_sources = commander_bodies.pop(card.name)
                    bodies[:] = [b for b in bodies if b is not body]
                    sources[:] = [src for src in sources if not any(src is m for m in made_sources)]
                    command.append(card)
        spells = [c for c in hand if not is_land(c)] + [_taxed(c, COMMANDER_TAX * commander_casts[c.name]) for c in command]
        land = _play_land([c for c in hand if is_land(c)], spells, sources, turn, library, lands_in_play)
        if land is not None:
            hand.remove(land)
            wanted = set(re.findall(r"[WUBRG]", "".join(c.mana_cost for c in spells)))
            colors, tapped, found = _landing(land, library, wanted, sources, lands_in_play)
            if found is not None:
                library.remove(found)
            if colors:
                sources.append(_Source(colors, turn + 1 if tapped else turn))
                lands_in_play += 1
        else:
            missed = True
        result["land_drops"].append(not missed)

        ready = [s.colors for s in sources if s.ready <= turn]
        spent = 0
        for card, amount in _plan(spells, ready):
            spent += amount
            cast_turn.setdefault(card.name, turn)
            commander = next((c for c in command if c.name == card.name), None)
            if card in hand:
                hand.remove(card)
            elif commander is not None:
                command.remove(commander)
                commander_casts[card.name] += 1
                if commander_casts[card.name] == 2:
                    recast_turn[card.name] = turn
            made = mana_sources(card)
            added = [_Source(colors, turn if "Artifact" in card.type_line else turn + 1) for colors in made]
            sources += added
            body = _Body(_power(card), turn if "Haste" in card.oracle_text else turn + 1) if "Creature" in card.type_line else None
            if body is not None:
                bodies.append(body)
            if commander is not None:
                commander_bodies[card.name] = (body, added)
        result["available"].append(len(ready))
        result["spent"].append(spent)
        result["stuck"].append(_blocked_on_colors(hand + [_taxed(c, COMMANDER_TAX * commander_casts[c.name]) for c in command], ready))
        total_damage += sum(b.power for b in bodies if b.ready <= turn)
        result["damage"].append(total_damage)
    return result


def play_game(deck: Deck, n: int, turns: int, seed: int, on_the_play: bool, free_mulligan: bool, commander_dies_on: int | None = None) -> dict:
    """Game number `n`: it shuffles the same way for the same seed and deck size, so two decks of one size can be compared."""
    return _play(deck, turns, random.Random(f"{seed}-{n}"), on_the_play, free_mulligan, commander_dies_on)


def play_games(deck: Deck, games: int, turns: int, seed: int, on_the_play: bool, free_mulligan: bool,
               commander_dies_on: int | None = None) -> list[dict]:
    return [play_game(deck, n, turns, seed, on_the_play, free_mulligan, commander_dies_on) for n in range(games)]


def game_value(run: dict) -> int:
    """What one game was worth: all the mana it spent on spells plus the damage it dealt by the last turn."""
    return sum(run["spent"]) + run["damage"][-1]


def simulate(deck: Deck, games: int = 1000, turns: int = 8, seed: int = 0, on_the_play: bool = False,
             free_mulligan: bool | None = None, commander_dies_on: int | None = None) -> SimStats:
    """Play `deck` alone `games` times for `turns` turns. A commander deck gets the free first mulligan unless told otherwise.
    With `commander_dies_on`, a commander on the battlefield goes back to the command zone at the start of that turn."""
    if free_mulligan is None:
        free_mulligan = bool(deck.commanders)
    return summarize(deck, play_games(deck, games, turns, seed, on_the_play, free_mulligan, commander_dies_on), turns)


def summarize(deck: Deck, runs: list[dict], turns: int) -> SimStats:
    """The report for finished games. A run is a dict as `_play` returns it; one from the engine goldfish (`goldfish.py`) may also have
    "drawn" and "permanents" (a number per turn)."""
    games = len(runs)
    mulliganed = opening_lands = 0
    drops, available, spent = ([0.0] * turns for _ in range(3))
    stuck, damage = [0] * turns, [0.0] * turns
    drawn, permanents = [0.0] * turns, [0.0] * turns
    copies: dict[str, int] = defaultdict(int)
    for card in deck.commanders + deck.main:
        if not is_land(card):
            copies[card.name] += 1
    seen, cast = defaultdict(int), defaultdict(int)
    cast_turns, waits = defaultdict(list), defaultdict(list)
    due_games, due_cast = defaultdict(int), defaultdict(int)
    total_casts, recast_turns = defaultdict(int), defaultdict(list)
    mana_value = {c.name: int(c.cmc) for c in deck.commanders + deck.main}
    for run in runs:
        mulliganed += run["mulligans"] > 0
        for name, times in run["casts"].items():
            total_casts[name] += times
        for name, turn in run["recast"].items():
            recast_turns[name].append(turn)
        opening_lands += run["opening_lands"]
        for i in range(turns):
            drops[i] += run["land_drops"][i]
            available[i] += run["available"][i]
            spent[i] += run["spent"][i]
            stuck[i] += run["stuck"][i]
            damage[i] += run["damage"][i]
            if "drawn" in run:
                drawn[i] += run["drawn"][i]
                permanents[i] += run["permanents"][i]
        for name, turn in run["seen"].items():
            if name not in copies:
                continue  # (a card the engine gave the player that is not in the deck)
            seen[name] += 1
            due = max(turn, mana_value[name], 1)  # the first turn the mana value and the draw allowed it
            if due <= turns:
                due_games[name] += 1
                due_cast[name] += run["cast"].get(name, turns + 1) <= due
            if name in run["cast"]:
                cast[name] += 1
                cast_turns[name].append(run["cast"][name])
                waits[name].append(run["cast"][name] - turn)
    games = games or 1
    avg = lambda values: round(sum(values) / len(values), 2) if values else None  # noqa: E731
    cards = [CardStats(name, copies[name], round(seen[name] / games, 3), round(cast[name] / games, 3),
                       round(cast[name] / seen[name], 3) if seen[name] else 0.0, avg(cast_turns[name]), avg(waits[name]),
                       round(due_cast[name] / due_games[name], 3) if due_games[name] else None,
                       round(total_casts[name] / games, 2) if name in total_casts else round(cast[name] / games, 2),
                       round(len(recast_turns[name]) / games, 3), avg(recast_turns[name]))
             for name in copies]
    per_turn = lambda values, digits=3: {i + 1: round(v / games, digits) for i, v in enumerate(values)}  # noqa: E731
    has_engine_columns = any("drawn" in run for run in runs)
    return SimStats(games=len(runs), turns=turns, mulligan_rate=round(mulliganed / games, 3),
                    average_opening_lands=round(opening_lands / games, 2), land_drop_rate=per_turn(drops),
                    mana_available=per_turn(available, 2), mana_spent=per_turn(spent, 2),
                    stuck_on_colors=per_turn(stuck), damage=per_turn(damage, 1), cards=cards,
                    drawn=per_turn(drawn, 2) if has_engine_columns else {}, permanents=per_turn(permanents, 1) if has_engine_columns else {})


def format_simulation(stats: SimStats) -> str:
    lines = [f"{stats.games} games, {stats.turns} turns. Mulligan rate {stats.mulligan_rate:.1%}, "
             f"{stats.average_opening_lands} lands in the opening hand, {stats.mana_efficiency:.0%} of available mana spent.",
             *([f"On curve: {stats.on_curve:.0%} of the spells drawn were cast as soon as their mana value allowed."] if stats.on_curve is not None else []),
             "", "turn  land drop  mana  spent  color-stuck  damage"]
    for turn in range(1, stats.turns + 1):
        lines.append(f"{turn:>4}  {stats.land_drop_rate[turn]:>9.1%}  {stats.mana_available[turn]:>4.1f}  {stats.mana_spent[turn]:>5.1f}  "
                     f"{stats.stuck_on_colors[turn]:>11.1%}  {stats.damage[turn]:>6.1f}")
    lines += ["", "card                                  copies  seen  cast  cast if seen  avg turn  avg wait  on curve"]
    for card in sorted(stats.cards, key=lambda c: (c.cast_when_seen, c.name)):
        turn = f"{card.average_cast_turn:.1f}" if card.average_cast_turn is not None else "-"
        wait = f"{card.average_wait:.1f}" if card.average_wait is not None else "-"
        curve = f"{card.on_curve:.0%}" if card.on_curve is not None else "-"
        lines.append(f"{card.name[:36]:<36}  {card.copies:>6}  {card.seen_rate:>4.0%}  {card.cast_rate:>4.0%}  {card.cast_when_seen:>11.0%}  {turn:>8}  {wait:>8}  {curve:>8}")
    recast = [c for c in stats.cards if c.recast_rate]
    if recast:
        lines += ["", "commander recast (each recast costs {2} more):"]
        lines += [f"  {c.name[:36]:<36}  first cast turn {c.average_cast_turn}, cast again in {c.recast_rate:.0%} of games, on turn {c.average_recast_turn} on average"
                  for c in recast]
    lines += ["", "Card text is not played here, only mana and creature bodies: removal, card draw and the like show up as mana spent."]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--play", action="store_true", help="be on the play (no draw on turn 1)")
    parser.add_argument("--commander-dies", type=int, metavar="TURN", help="send commanders back to the command zone at the start of this turn")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(args.bulk))
    print(format_simulation(simulate(deck, args.games, args.turns, args.seed, args.play, commander_dies_on=args.commander_dies)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
