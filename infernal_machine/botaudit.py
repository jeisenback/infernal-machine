"""Which cards does the bot see and not cast? (issue #407)

    python -m infernal_machine.botaudit DECKLIST [--games 200] [--turns 10] [--seed 0] [--workers N] [--top 25] [--all]

The engine goldfish (`goldfish.py`) plays the deck alone through the real engine and records, for every nonland card, the turns it
sat in the bot's hand, the turns the game *offered* to cast it, and what the bot did on the turns it was offered and not cast. A card
seen often and cast rarely is one of two things, and the numbers say which:

- **never offered**: the game did not list casting it on (almost) any turn it was in hand, so the bot was never in a position to
  choose: a cost it can't pay, colours its lands don't make, a target or condition the game wants first. If the fast model casts it
  and the engine does not, the engine reads something about the card the model doesn't (or the lands, tapped or off-colour, do).
- **offered, passed over**: the game offered it and the bot chose something else, listed with how often. That is the bot's blind spot,
  for example rituals it won't cast, or a spell it holds on purpose.

A card both the engine and the model rarely cast is just expensive or off-colour, and is listed last. Cards seen in fewer than
`MIN_SEEN` games are left out: there is nothing to go on. The model's casts come from `simulate.simulate` on the same seed.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

from .analysis import is_land
from .bot import _is_creature_removal, _is_ritual, _is_wipe
from .cards import Card, Deck
from .goldfish import play_runs
from .simulate import SimStats, simulate, summarize

MIN_SEEN = 8  # games a card must be seen in before anything is said about it
LOW = 0.5  # a card cast in less than this share of the games it was seen in is listed
NEEDS_TARGET = "needs a target or graveyard cards the goldfish lacks"
ON_PURPOSE = "held on purpose (the bot's own rule)"
HARD = "rarely castable (the model agrees)"
_TARGET = re.compile(r"\btarget (?:[\w-]+ ){0,3}(?:creature|permanent|spell|opponent|player|planeswalker|artifact|enchantment|land)s?\b(?! you control)"
                     r"|\bany target\b|\beach opponent\b|\bcounter target\b|\bgraveyard\b", re.I)
RARELY_OFFERED = 0.15  # of the turns it sat in hand, a card offered on fewer than this share is one the game does not offer


@dataclass
class AuditRow:
    name: str
    copies: int
    seen_games: int
    cast_when_seen: float  # the engine's
    model_cast_when_seen: float | None  # the fast model's
    held_turns: int  # turns (over all games) it was in hand at the start of the first main phase
    offered_turns: int  # of those turns, the ones on which casting it was offered in a main phase
    passed_turns: int = 0  # the offered turns that ended without it cast
    passed_for: list[tuple[str, int]] = field(default_factory=list)  # what the bot cast instead on those turns
    needs_target: bool = False  # its text wants a target (an opposing creature, a spell) or a graveyard the goldfish does not have
    on_purpose: str = ""  # the bot's own rule for not casting it (a wipe, a ritual, removal held for a threat), if it has one

    @property
    def offered_rate(self) -> float:
        return self.offered_turns / self.held_turns if self.held_turns else 0.0

    @property
    def gap(self) -> float:
        """How much more often the model casts it when it is seen than the engine does."""
        return (self.model_cast_when_seen or 0.0) - self.cast_when_seen

    @property
    def verdict(self) -> str:
        if self.on_purpose:
            return ON_PURPOSE
        if self.needs_target:
            return NEEDS_TARGET
        if self.offered_rate < RARELY_OFFERED:
            return "never offered" if self.gap > 0.15 else HARD
        if self.offered_turns and self.passed_turns / self.offered_turns >= 0.5:
            return "offered, passed over"
        return HARD


def _on_purpose(card: Card) -> str:
    """Why the bot does not cast this card, when it is one of its own rules: a wipe waits until the opponents have more creatures, a
    ritual is not cast on its own, removal for a creature waits for a threat."""
    if _is_wipe(card):
        return "a wipe: cast only when opponents have more creatures than it does"
    if _is_ritual(card):
        return "a ritual: never cast on its own"
    if _is_creature_removal(card):
        return "creature removal: held until a creature is worth it"
    return ""


def audit_rows(deck: Deck, runs: list[dict], turns: int, model: SimStats | None = None) -> list[AuditRow]:
    """The cards of `deck` the engine goldfish saw and rarely cast, worst first: the bot's blind spots (offered, passed over), then the
    cards the game does not offer, then the ones the model finds hard too."""
    stats = {c.name: c for c in summarize(deck, runs, turns).cards}
    modelled = {c.name: c for c in model.cards} if model else {}
    held, offered, passed_turns = Counter(), Counter(), Counter()
    passed: dict[str, Counter] = {}
    cards = {c.name: c for c in deck.commanders + deck.main}
    for run in runs:
        for name, count in run["held"].items():
            held[name] += count
        for name, on in run["offered"].items():
            offered[name] += len(on)
        for name, instead in run["passed"].items():
            passed.setdefault(name, Counter()).update(instead)
        for name, count in run["passed_turns"].items():
            passed_turns[name] += count
    rows = []
    for name, card in stats.items():
        seen_games = round(card.seen_rate * len(runs))
        if seen_games < MIN_SEEN or card.cast_when_seen >= LOW:
            continue
        reference = modelled.get(name)
        rows.append(AuditRow(name, card.copies, seen_games, card.cast_when_seen, reference.cast_when_seen if reference else None,
                             held[name], offered[name], passed_turns[name], passed.get(name, Counter()).most_common(3),
                             bool(_TARGET.search(cards[name].oracle_text)) if name in cards else False,
                             _on_purpose(cards[name]) if name in cards else ""))
    order = {"offered, passed over": 0, "never offered": 1, ON_PURPOSE: 3, NEEDS_TARGET: 4}
    rows.sort(key=lambda r: (order.get(r.verdict, 2), -r.gap, -r.seen_games, r.name))
    return rows


def audit(deck: Deck, games: int = 200, turns: int = 10, seed: int = 0, workers: int = 1, model_games: int = 1000) -> tuple[list[AuditRow], int]:
    """(the rows, the games that could not be finished)."""
    runs = play_runs(deck, games, turns, seed, False, workers)
    finished = [r for r in runs if r is not None]
    model = simulate(deck, model_games, turns, seed) if model_games else None
    return audit_rows(deck, finished, turns, model), len(runs) - len(finished)


def format_audit(rows: list[AuditRow], games: int, dropped: int = 0, top: int = 25, everything: bool = False) -> str:
    shown = rows if everything else [r for r in rows if r.verdict not in (HARD, NEEDS_TARGET, ON_PURPOSE)]
    lines = [f"{games} engine games. Cards seen in at least {MIN_SEEN} games and cast in under {LOW:.0%} of the games they were seen in:", ""]
    if not shown:
        lines.append("None: every card seen often enough is cast when it is seen.")
    for verdict in ("offered, passed over", "never offered", HARD, ON_PURPOSE, NEEDS_TARGET):
        group = [r for r in shown if r.verdict == verdict][:top]
        if not group:
            continue
        lines += [f"{verdict}:", "  card                                  seen  cast  model  offered  passed  what the bot cast instead"]
        for r in group:
            model = f"{r.model_cast_when_seen:.0%}" if r.model_cast_when_seen is not None else "-"
            instead = r.on_purpose if r.on_purpose else ", ".join(f"{what} x{n}" for what, n in r.passed_for) or "-"
            lines.append(f"  {r.name[:36]:<36}  {r.seen_games:>4}  {r.cast_when_seen:>4.0%}  {model:>5}  {r.offered_rate:>7.0%}  {r.passed_turns:>6}  {instead}")
        lines.append("")
    if dropped:
        lines.append(f"{dropped} game(s) could not be finished and are left out.")
    lines.append('"offered" is the share of the turns a card sat in hand on which the game listed casting it, "passed" the turns it was offered '
                 "and not cast. A card the game never offers is not the bot's choice; one it offers and the bot passes over is. "
                 "Cards held by one of the bot's own rules, and cards that need an opposing target or cards in a graveyard (a goldfish has few), are not judged "
                 "here; --all lists them.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    import os

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--top", type=int, default=25, help="rows per group")
    parser.add_argument("--all", action="store_true", help="also list the cards the model finds hard to cast too, and those that need a target")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(args.bulk))
    rows, dropped = audit(deck, args.games, args.turns, args.seed, args.workers)
    print(format_audit(rows, args.games - dropped, dropped, args.top, args.all))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
