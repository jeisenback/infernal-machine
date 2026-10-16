"""Measure what a card adds in real games, so removal, card draw and counterspells get a score.

    python -m infernal_machine.impact DECKLIST OPPONENT [OPPONENT ...] [--cards "Card Name"]... [--top 12] [--games 40] [--pod N] [--workers N]

`tune` scores a card by replaying goldfish games with it swapped for a blank, and the goldfish reads no card text, so a removal spell
scores as mana spent and a counterspell as nothing. Here the cards are measured against other decks: the baseline games are played once,
then for each chosen card the *same* games (same seeds, seats and opponents: `matchup.plan_games`, as `compare` does) are played with
every copy of the card replaced by a blank, and the card's impact is the baseline's score minus the blank's, per pair, with a 95%
interval from the spread of those differences. A blank takes the card's slot, so the deck keeps its size and the shuffles stay
paired. By default the cards measured are the ones the goldfish scores lowest, since those are where its blindness to text matters.

A commander is not measured (taking it out leaves the deck without its color identity and its command zone). The bots play every game,
so a card they play badly is under-rated; and the more cards are tested the more likely one looks clear by chance: about one in twenty
at 95%. Re-run the ones you act on with another `--seed`. Cards the engine can't read are marked, since the games cannot see their text.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from .cards import Deck
from .compare import Z, pair_up, score, summarize
from .matchup import play_plans, plan_games
from .report import unsupported_lines
from .tune import BLANK, tune


MIN_DIFFERING = 8  # fewer differing pairs than this and the spread of the differences, and so a pairs-needed estimate, rests on too few events


@dataclass
class CardGameImpact:
    card: str
    copies: int
    pairs: int  # games played with and without it, both finished
    impact: float  # the card's score minus the blank's, averaged over the pairs: what it adds (1.0 is a whole game)
    error: float  # the standard error of that
    differing: int  # pairs that came out differently; the rest say nothing about the card
    unreadable: str | None = None  # the first line of its text the engine can't read
    needed: int | None = None  # pairs it would take to resolve a 5 point impact at this spread; None if fewer than MIN_DIFFERING pairs differed

    @property
    def interval(self) -> tuple[float, float]:
        return self.impact - Z * self.error, self.impact + Z * self.error

    @property
    def clear(self) -> bool:
        low, high = self.interval
        return low > 0 or high < 0


@dataclass
class ImpactReport:
    games: int  # paired games per opponent (in all, for a pod)
    opponents: list[str]
    baseline_score: float
    impacts: list[CardGameImpact]  # weakest first
    notes: list[str] = field(default_factory=list)


def blanked(deck: Deck, name: str) -> Deck:
    """The deck with every copy of `name` replaced by a blank: same size, same slots."""
    return replace(deck, main=[BLANK if card.name == name else card for card in deck.main])


def weakest_cards(deck: Deck, count: int, games: int = 300, turns: int = 8, seed: int = 0) -> list[str]:
    """The `count` cards the goldfish scores lowest (those it was drawn at least once), commanders left out."""
    commanders = {card.name for card in deck.commanders}
    report = tune(deck, games, turns, seed)
    return [c.name for c in report.cards if c.seen_rate and c.name not in commanders][:count]


def measure_impacts(deck: Deck, opponents: dict[str, Deck], cards: list[str] | None = None, *, top: int = 12, games: int = 40, pod: int = 2,
                    seed: int = 0, max_turns: int = 60, time_limit: float = 120.0, workers: int = 1, goldfish_games: int = 300,
                    goldfish_turns: int = 8, progress: Callable[[str], None] | None = None) -> ImpactReport:
    """Play the baseline and, for each card, the same games with the card blanked. `cards` names them; by default the `top` that the
    goldfish scores lowest."""
    in_deck = {card.name: card for card in deck.main}
    commanders = {card.name for card in deck.commanders}
    for name in cards or []:
        if name in commanders:
            raise ValueError(f"{name} is a commander, and a commander is not measured (taking it out leaves the deck without its colors)")
        if name not in in_deck:
            raise ValueError(f"{name} is not in the main deck")
    say = progress or (lambda message: None)
    if cards is None:
        say("Choosing the cards the goldfish scores lowest...")
        cards = weakest_cards(deck, top, goldfish_games, goldfish_turns, seed)
    plan = lambda d: plan_games(d, opponents, games, pod, seed, max_turns, time_limit)  # noqa: E731
    say("Baseline...")
    base_plan = plan(deck)
    names = [name for name, _ in base_plan]
    base = play_plans(base_plan, workers)
    finished = [score(result) for group in base for result in group if result.error is None]
    baseline_score = sum(finished) / len(finished) if finished else 0.0
    impacts = []
    for i, name in enumerate(cards, 1):
        say(f"{name} ({i}/{len(cards)})...")
        variant = play_plans(plan(blanked(deck, name)), workers)
        comparison = summarize(*pair_up(base, variant, names))
        copies = sum(1 for card in deck.main if card.name == name)
        lines = unsupported_lines(in_deck[name])
        differing = comparison.changed_better + comparison.baseline_better
        impacts.append(CardGameImpact(name, copies, comparison.pairs, -comparison.difference, comparison.error, differing, lines[0] if lines else None,
                                      comparison.pairs_needed(0.05) if differing >= MIN_DIFFERING else None))
    impacts.sort(key=lambda c: (c.impact / c.copies, c.card))
    notes = ["Most pairs come out identical (the 'differ' column): a card is drawn in only a fraction of games, and often changes nothing when it is. "
             "'For 5 pts' is about how many pairs it takes to resolve a 5 point impact at that spread; a dash means fewer than "
             f"{MIN_DIFFERING} pairs differed, too few to estimate it."]
    if len(impacts) > 1:
        notes.append(f"{len(impacts)} cards were tested: about one in twenty would look clear by chance. Re-run the ones you act on with another --seed.")
    unreadable = [c.card for c in impacts if c.unreadable]
    if unreadable:
        notes.append(f"The engine can't fully play {', '.join(unreadable)}: it casts them and ignores the text it can't read, so these games cannot see what that text does.")
    return ImpactReport(games, list(opponents), baseline_score, impacts, notes)


def format_impacts(report: ImpactReport) -> str:
    where = f"against {', '.join(report.opponents)}" if len(report.opponents) <= 3 else f"against {len(report.opponents)} opponents"
    lines = [f"Card impact in real games: {report.games} paired games {where} for each of {len(report.impacts)} cards. The same games are played "
             "with every copy of the card replaced by a blank; the impact is the score the card adds (a win is 1, a draw 1/2), in points.",
             f"The unchanged deck scores {report.baseline_score:.1%}.", "",
             "card                                  copies  impact                       pairs  differ  for 5 pts  note"]
    for c in report.impacts:
        low, high = c.interval
        tag = "" if c.clear else "  (within noise)"
        note = f"can't read: {c.unreadable[:40]}" if c.unreadable else ""
        needed = str(c.needed) if c.needed else "-"
        lines.append(f"{c.card[:36]:<36}  {c.copies:>6}  {c.impact * 100:+6.1f} ±{c.error * 100:4.1f}{tag:<16}  {c.pairs:>5}  {c.differing:>6}  {needed:>9}  {note}")
    lines += ["", *report.notes]
    return "\n".join(lines).rstrip("\n")


def main(argv: list[str], source=None) -> int:
    import argparse
    import os

    from .cards import BulkSource, CardNotFound, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("opponents", nargs="+", help="decklists to play against")
    parser.add_argument("--cards", action="append", default=None, metavar="CARD", help="a card to measure (repeat for several); default: the weakest by goldfish")
    parser.add_argument("--top", type=int, default=12, help="how many of the goldfish's lowest scores to measure")
    parser.add_argument("--games", type=int, default=40, help="paired games per opponent (in all, with --pod)")
    parser.add_argument("--pod", type=int, default=2, help="players per game; above 2 draws the opponents at random")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--time-limit", type=float, default=120.0, help="seconds per game")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--goldfish-games", type=int, default=300, help="games for choosing the weakest cards")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    source = source or BulkSource(args.bulk)
    name = lambda path: os.path.splitext(os.path.basename(path))[0]  # noqa: E731

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return load_deck(f.read(), source)

    try:
        report = measure_impacts(load(args.decklist), {name(p): load(p) for p in args.opponents}, args.cards, top=args.top, games=args.games,
                                 pod=args.pod, seed=args.seed, max_turns=args.max_turns, time_limit=args.time_limit, workers=args.workers,
                                 goldfish_games=args.goldfish_games, progress=lambda m: print(m, file=sys.stderr, flush=True))
    except (CardNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(format_impacts(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
