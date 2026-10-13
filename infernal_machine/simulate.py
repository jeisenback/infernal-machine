"""Goldfish simulation: play a deck alone and measure how its mana and curve behave.

    python -m infernal_machine.simulate DECKLIST [--games N] [--turns N] [--seed N] [--play]

Each game uses the bot's mulligan rules, draws a card a turn, plays one land a turn, and casts whatever it can pay for
(color by color, through `mana.pay`). It models mana and bodies only, not rules text: a spell is cast when its mana
cost can be paid, and nothing else it does is simulated except that creatures attack for their power from the turn
after they enter (or at once with haste). Mana rocks and mana creatures count as sources. Conditional "enters tapped"
lands and shocklands are treated as untapped, X is 0, and commanders are cast once with no tax, so the numbers are
for comparing builds, not for predicting a game. Works for any format: pass a 60-card list for Standard.
"""

from __future__ import annotations

import io
import random
import re
import sys
from collections import defaultdict
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


def _play_land(lands: list[Card], spells: list[Card], sources: list[_Source], turn: int) -> Card | None:
    """The land to play: the one that lets the most mana be spent this turn, then the one that covers the most colors
    the hand's spells ask for, preferring an untapped land."""
    wanted = set(re.findall(r"[WUBRG]", "".join(c.mana_cost for c in spells)))
    best, best_key = None, None
    for land in {(land_colors(l), enters_tapped(l)): l for l in lands}.values():
        tapped = enters_tapped(land)
        now = [s.colors for s in sources if s.ready <= turn] + ([] if tapped else [land_colors(land)])
        key = (sum(n for _, n in _plan(spells, now)), len(land_colors(land) & wanted), not tapped, len(land_colors(land)))
        if best_key is None or key > best_key:
            best, best_key = land, key
    return best


def _play(deck: Deck, turns: int, rng: random.Random, on_the_play: bool, free_mulligan: bool) -> dict:
    hand, library, mulligans = opening_hand(deck.main, rng, free_mulligan)
    command = list(deck.commanders)
    sources: list[_Source] = []
    bodies: list[_Body] = []
    seen_turn: dict[str, int] = {c.name: 0 for c in hand + command if not is_land(c)}
    cast_turn: dict[str, int] = {}
    result = {"mulligans": mulligans, "opening_lands": sum(1 for c in hand if is_land(c)), "land_drops": [], "available": [],
              "spent": [], "stuck": [], "damage": [], "seen": seen_turn, "cast": cast_turn}
    missed = False
    total_damage = 0
    for turn in range(1, turns + 1):
        if library and not (turn == 1 and on_the_play):
            card = library.pop(0)
            hand.append(card)
            if not is_land(card):
                seen_turn.setdefault(card.name, turn)
        spells = [c for c in hand if not is_land(c)] + [c for c in command if c.name not in cast_turn]
        land = _play_land([c for c in hand if is_land(c)], spells, sources, turn)
        if land is not None:
            hand.remove(land)
            sources.append(_Source(land_colors(land), turn + 1 if enters_tapped(land) else turn))
        else:
            missed = True
        result["land_drops"].append(not missed)

        ready = [s.colors for s in sources if s.ready <= turn]
        spent = 0
        for card, amount in _plan(spells, ready):
            spent += amount
            cast_turn.setdefault(card.name, turn)
            if card in hand:
                hand.remove(card)
            else:
                command.remove(card)
            made = mana_sources(card)
            if made:
                sources += [_Source(colors, turn if "Artifact" in card.type_line else turn + 1) for colors in made]
            if "Creature" in card.type_line:
                bodies.append(_Body(_power(card), turn if "Haste" in card.oracle_text else turn + 1))
        result["available"].append(len(ready))
        result["spent"].append(spent)
        result["stuck"].append(_blocked_on_colors(hand + [c for c in command if c.name not in cast_turn], ready))
        total_damage += sum(b.power for b in bodies if b.ready <= turn)
        result["damage"].append(total_damage)
    return result


def play_game(deck: Deck, n: int, turns: int, seed: int, on_the_play: bool, free_mulligan: bool) -> dict:
    """Game number `n`: it shuffles the same way for the same seed and deck size, so two decks of one size can be compared."""
    return _play(deck, turns, random.Random(f"{seed}-{n}"), on_the_play, free_mulligan)


def play_games(deck: Deck, games: int, turns: int, seed: int, on_the_play: bool, free_mulligan: bool) -> list[dict]:
    return [play_game(deck, n, turns, seed, on_the_play, free_mulligan) for n in range(games)]


def game_value(run: dict) -> int:
    """What one game was worth: all the mana it spent on spells plus the damage it dealt by the last turn."""
    return sum(run["spent"]) + run["damage"][-1]


def simulate(deck: Deck, games: int = 1000, turns: int = 8, seed: int = 0, on_the_play: bool = False,
             free_mulligan: bool | None = None) -> SimStats:
    """Play `deck` alone `games` times for `turns` turns. A commander deck gets the free first mulligan unless told otherwise."""
    if free_mulligan is None:
        free_mulligan = bool(deck.commanders)
    mulliganed = opening_lands = 0
    drops, available, spent = ([0.0] * turns for _ in range(3))
    stuck, damage = [0] * turns, [0.0] * turns
    copies: dict[str, int] = defaultdict(int)
    for card in deck.commanders + deck.main:
        if not is_land(card):
            copies[card.name] += 1
    seen, cast = defaultdict(int), defaultdict(int)
    cast_turns, waits = defaultdict(list), defaultdict(list)
    for run in play_games(deck, games, turns, seed, on_the_play, free_mulligan):
        mulliganed += run["mulligans"] > 0
        opening_lands += run["opening_lands"]
        for i in range(turns):
            drops[i] += run["land_drops"][i]
            available[i] += run["available"][i]
            spent[i] += run["spent"][i]
            stuck[i] += run["stuck"][i]
            damage[i] += run["damage"][i]
        for name, turn in run["seen"].items():
            seen[name] += 1
            if name in run["cast"]:
                cast[name] += 1
                cast_turns[name].append(run["cast"][name])
                waits[name].append(run["cast"][name] - turn)
    avg = lambda values: round(sum(values) / len(values), 2) if values else None  # noqa: E731
    cards = [CardStats(name, copies[name], round(seen[name] / games, 3), round(cast[name] / games, 3),
                       round(cast[name] / seen[name], 3) if seen[name] else 0.0, avg(cast_turns[name]), avg(waits[name]))
             for name in copies]
    per_turn = lambda values, digits=3: {i + 1: round(v / games, digits) for i, v in enumerate(values)}  # noqa: E731
    return SimStats(games=games, turns=turns, mulligan_rate=round(mulliganed / games, 3),
                    average_opening_lands=round(opening_lands / games, 2), land_drop_rate=per_turn(drops),
                    mana_available=per_turn(available, 2), mana_spent=per_turn(spent, 2),
                    stuck_on_colors=per_turn(stuck), damage=per_turn(damage, 1), cards=cards)


def format_simulation(stats: SimStats) -> str:
    lines = [f"{stats.games} games, {stats.turns} turns. Mulligan rate {stats.mulligan_rate:.1%}, "
             f"{stats.average_opening_lands} lands in the opening hand, {stats.mana_efficiency:.0%} of available mana spent.",
             "", "turn  land drop  mana  spent  color-stuck  damage"]
    for turn in range(1, stats.turns + 1):
        lines.append(f"{turn:>4}  {stats.land_drop_rate[turn]:>9.1%}  {stats.mana_available[turn]:>4.1f}  {stats.mana_spent[turn]:>5.1f}  "
                     f"{stats.stuck_on_colors[turn]:>11.1%}  {stats.damage[turn]:>6.1f}")
    lines += ["", "card                                  copies  seen  cast  cast if seen  avg turn  avg wait"]
    for card in sorted(stats.cards, key=lambda c: (c.cast_when_seen, c.name)):
        turn = f"{card.average_cast_turn:.1f}" if card.average_cast_turn is not None else "-"
        wait = f"{card.average_wait:.1f}" if card.average_wait is not None else "-"
        lines.append(f"{card.name[:36]:<36}  {card.copies:>6}  {card.seen_rate:>4.0%}  {card.cast_rate:>4.0%}  {card.cast_when_seen:>11.0%}  {turn:>8}  {wait:>8}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--play", action="store_true", help="be on the play (no draw on turn 1)")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(args.bulk))
    print(format_simulation(simulate(deck, args.games, args.turns, args.seed, args.play)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
