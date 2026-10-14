"""Tuning report: which cards earn their slot, and what a different land count or a candidate card would do.

    python -m infernal_machine.tune DECKLIST [--games N] [--turns N] [--seed N] [--try "Card Name"]...

It scores a deck by what `simulate` sees: the mana a game spends on spells plus the damage it deals by the last turn
(`game_value`). To measure a card it replays the same games with that card replaced by a blank, so every shuffle is
the same and the difference is the card's contribution; only the games where the card was drawn can differ, so only
those are replayed. This rewards deploying mana and creatures. It cannot see what a card's text does (removal, card
draw, counterspells, life gain), so a low score means "does little in a goldfish", not "bad card": read it next to the
card's job in the deck.
"""

from __future__ import annotations

import io
import math
import sys
from collections import Counter
from dataclasses import dataclass, field, replace

from .analysis import is_land
from .cards import Card, Deck
from .commander import copy_limit
from .simulate import game_value, play_game, play_games

BLANK = Card(name="(blank)", type_line="Sorcery")  # no cost, so it is never cast: a dead card in the same slot
DEAD_WEIGHT = 0.5  # cast less often than this when drawn, and it is flagged


@dataclass
class Effect:
    """A change's average effect on a game's value, over all games, with its standard error."""
    delta: float
    error: float

    @property
    def clear(self) -> bool:
        return abs(self.delta) > 2 * self.error


@dataclass
class CardImpact:
    name: str
    copies: int
    value: Effect  # what the card adds per game (with it minus without it)
    seen_rate: float
    cast_when_seen: float
    note: str = ""


@dataclass
class TuningReport:
    games: int
    turns: int
    baseline: float  # average game value
    cards: list[CardImpact]  # weakest first
    lands: dict[int, Effect]  # change in land count -> effect on value
    swaps: list[tuple[str, str, Effect]] = field(default_factory=list)  # (card tried, card it replaces, effect), best first
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (candidate, why it was not tried)


def candidate_problem(deck: Deck, card: Card) -> str | None:
    """Why `card` can't be swapped into `deck`, or None. A Commander deck (one with a commander) needs the card inside the
    commander's color identity, legal in Commander, and not past its copy limit (singleton, so a card already in it is out)."""
    in_deck = sum(1 for c in deck.main + deck.commanders if c.name == card.name)
    if not deck.commanders:
        return "already at four copies" if in_deck >= 4 and "Basic" not in card.type_line else None
    identity = {color for c in deck.commanders for color in c.color_identity}
    if set(card.color_identity) - identity:
        return f"outside the commander's color identity ({''.join(sorted(set(card.color_identity) - identity))})"
    if not card.commander_legal:
        return "not legal in Commander"
    limit = copy_limit(card)
    if limit is not None and in_deck >= limit:
        return "already in the deck" if limit == 1 else f"already at the limit of {limit}"
    return None


def _effect(deltas: list[float]) -> Effect:
    n = len(deltas)
    mean = sum(deltas) / n
    variance = sum((d - mean) ** 2 for d in deltas) / (n - 1) if n > 1 else 0.0
    return Effect(round(mean, 2), round(math.sqrt(variance / n), 2))


def _swapped(deck: Deck, replacements: dict[int, Card], commanders: dict[int, Card] | None = None) -> Deck:
    main = [replacements.get(i, card) for i, card in enumerate(deck.main)]
    return replace(deck, main=main, commanders=[(commanders or {}).get(i, c) for i, c in enumerate(deck.commanders)])


def _deltas(deck: Deck, changed: Deck, base: list[dict], games: int, turns: int, seed: int, play: bool, free: bool,
            only: set[int] | None = None) -> list[float]:
    """Per game, the changed deck's value minus the base deck's: the games outside `only` are known to be the same."""
    rerun = sorted(only) if only is not None else range(games)
    deltas = [0.0] * games
    for n in rerun:
        deltas[n] = game_value(play_game(changed, n, turns, seed, play, free)) - game_value(base[n])
    return deltas


def tune(deck: Deck, games: int = 500, turns: int = 8, seed: int = 0, candidates: list[Card] | None = None,
         on_the_play: bool = False, free_mulligan: bool | None = None) -> TuningReport:
    if free_mulligan is None:
        free_mulligan = bool(deck.commanders)
    base = play_games(deck, games, turns, seed, on_the_play, free_mulligan)
    args = (base, games, turns, seed, on_the_play, free_mulligan)
    seen_in: dict[str, set[int]] = {}
    cast_in: Counter = Counter()
    for n, run in enumerate(base):
        for name in run["seen"]:
            seen_in.setdefault(name, set()).add(n)
        cast_in.update(run["cast"].keys())

    slots: dict[str, list[int]] = {}
    for i, card in enumerate(deck.main):
        if not is_land(card):
            slots.setdefault(card.name, []).append(i)
    impacts = []
    for name, seen in seen_in.items():
        in_main = slots.get(name, [])
        in_command = [i for i, c in enumerate(deck.commanders) if c.name == name]
        if not in_main and not in_command:
            continue
        changed = _swapped(deck, {i: BLANK for i in in_main}, {i: BLANK for i in in_command})
        effect = _effect([-d for d in _deltas(deck, changed, *args, only=seen)])
        rate = cast_in[name] / len(seen)
        note = "rarely cast when drawn" if rate < DEAD_WEIGHT else ""
        impacts.append(CardImpact(name, len(in_main) + len(in_command), effect, round(len(seen) / games, 3), round(rate, 3), note))
    for name, indexes in slots.items():  # never drawn in any game: no evidence either way
        if name not in seen_in:
            impacts.append(CardImpact(name, len(indexes), Effect(0.0, 0.0), 0.0, 0.0, "never drawn in these games"))
    impacts.sort(key=lambda c: (c.value.delta / c.copies, c.name))

    baseline = sum(game_value(run) for run in base) / games
    legal, skipped = [], []
    for card in candidates or []:
        problem = candidate_problem(deck, card)
        (skipped.append((card.name, problem)) if problem else legal.append(card))
    return TuningReport(games, turns, round(baseline, 2), impacts, _land_sweep(deck, impacts, *args),
                        _swap_candidates(deck, impacts, legal, seen_in, *args), skipped)


def _land_sweep(deck: Deck, impacts: list[CardImpact], *args) -> dict[int, Effect]:
    """+k: the k weakest drawn nonland cards become the deck's most played basic land; -k: k lands become extra copies of
    a typical (median) card, which a singleton deck could not do but which prices a land slot against an average spell."""
    lands = Counter(c.name for c in deck.main if is_land(c))
    in_main = {i.name: [n for n, c in enumerate(deck.main) if c.name == i.name] for i in impacts if i.seen_rate}
    ranked = [i for i in impacts if in_main.get(i.name)]  # weakest first
    if not lands or not ranked:
        return {}
    land = next(c for c in deck.main if c.name == lands.most_common(1)[0][0])
    typical = next(c for c in deck.main if c.name == ranked[len(ranked) // 2].name)
    weak = [n for i in ranked for n in in_main[i.name]]
    land_slots = [n for n, c in enumerate(deck.main) if is_land(c)]
    out: dict[int, Effect] = {}
    for k in (1, 2, 3):
        if len(weak) >= k:
            out[k] = _effect(_deltas(deck, _swapped(deck, {n: land for n in weak[:k]}), *args))
        if len(land_slots) > k + 20:
            out[-k] = _effect(_deltas(deck, _swapped(deck, {n: typical for n in land_slots[:k]}), *args))
    return dict(sorted(out.items()))


def _swap_candidates(deck: Deck, impacts: list[CardImpact], candidates: list[Card], seen_in: dict[str, set[int]], *args):
    """Each candidate takes the place of the weakest card that isn't a commander; the effect is the change in value."""
    base, games, turns, seed, play, free = args
    in_main = {c.name: [i for i, card in enumerate(deck.main) if card.name == c.name] for c in deck.main}
    weakest = next((imp for imp in impacts if imp.seen_rate and in_main.get(imp.name)), None)
    if weakest is None:
        return []
    out = []
    slot = in_main[weakest.name][0]
    for card in candidates:
        deltas = _deltas(deck, _swapped(deck, {slot: card}), *args, only=seen_in.get(weakest.name, set()))
        out.append((card.name, weakest.name, _effect(deltas)))
    return sorted(out, key=lambda t: -t[2].delta)


def _plusminus(effect: Effect) -> str:
    return f"{effect.delta:+.2f} ±{effect.error:.2f}" + ("" if effect.clear else "  (within noise)")


def format_tuning(report: TuningReport) -> str:
    lines = [f"{report.games} games, {report.turns} turns. Average game value {report.baseline} "
             "(mana spent on spells + damage dealt by the last turn).", "",
             "Per card, weakest first: what the card adds per game, replayed with the card as a blank.",
             "card                                  copies  adds per game        seen  cast if seen  note"]
    for card in report.cards:
        lines.append(f"{card.name[:36]:<36}  {card.copies:>6}  {_plusminus(card.value):<20}  {card.seen_rate:>4.0%}  "
                     f"{card.cast_when_seen:>11.0%}  {card.note}")
    if report.lands:
        lines += ["", "Land count (change in lands -> change in value):"]
        lines += [f"  {k:+d} lands: {_plusminus(effect)}" for k, effect in report.lands.items()]
    if report.swaps:
        lines += ["", "Swaps (best first): the card replaces the weakest card in the deck."]
        lines += [f"  {new} for {old}: {_plusminus(effect)}" for new, old, effect in report.swaps]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import argparse

    from .cards import BulkSource, CardNotFound, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--play", action="store_true", help="be on the play (no draw on turn 1)")
    parser.add_argument("--try", dest="candidates", action="append", default=[], metavar="CARD", help="a card to test in the weakest slot")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    source = BulkSource(args.bulk)
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), source)
    try:
        candidates = [source.get(name) for name in args.candidates]
    except CardNotFound as error:
        print(f"unknown card: {error}", file=sys.stderr)
        return 2
    print(format_tuning(tune(deck, args.games, args.turns, args.seed, candidates, args.play)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
