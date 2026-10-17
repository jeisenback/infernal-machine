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
from .gauntlet import opponent_paths
from .compare import pair_up, score, stop_reason, summarize
from .matchup import play_plans, plan_games
from .report import unsupported_lines
from .sequential import MIN_DIFFERING, Z, confidence, look_z, schedule
from .tune import BLANK, tune


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
    z: float = Z  # the interval's width in standard errors (wider when the games were played in rounds and looked at between them)
    stopped: str | None = None  # "clear" or "hopeless" if it was dropped before the planned games were played

    @property
    def interval(self) -> tuple[float, float]:
        return self.impact - self.z * self.error, self.impact + self.z * self.error

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
    spent: int = 0  # games played (the baseline's and every card's) when it played in rounds
    budget: int = 0  # the games a fixed run would have played


def blanked(deck: Deck, name: str) -> Deck:
    """The deck with every copy of `name` replaced by a blank: same size, same slots."""
    return replace(deck, main=[BLANK if card.name == name else card for card in deck.main])


def weakest_cards(deck: Deck, count: int, games: int = 300, turns: int = 8, seed: int = 0) -> list[str]:
    """The `count` cards the goldfish scores lowest (those it was drawn at least once), commanders left out."""
    commanders = {card.name for card in deck.commanders}
    report = tune(deck, games, turns, seed)
    return [c.name for c in report.cards if c.seen_rate and c.name not in commanders][:count]


EXTEND = 3  # with early stopping, a card still undecided may be played up to this many times the games asked for, out of the games the others did not need


def _in_rounds(deck: Deck, opponents: dict[str, Deck], cards: list[str], games: int, pod: int, seed: int, max_turns: int, time_limit: float,
               workers: int, target: float, say: Callable[[str], None]):
    """The baseline and each card's blanked games, a round at a time. After each round a card whose impact is clearly away from zero, or
    out of reach for the games planned, is dropped (`compare.stop_reason`, with each look's interval widened for the number of looks), and
    the games it would have used go to the cards still undecided, up to `EXTEND` times `games` for any one card. The total never passes
    what a fixed run of `games` per card would play. Returns (the baseline results, the last comparison and why it stopped for each card,
    the games played, the games a fixed run plays, the looks, the interval width)."""
    most = games * EXTEND
    looks, batch = schedule(most)
    z = look_z(looks)
    plan = lambda d: plan_games(d, opponents, most, pod, seed, max_turns, time_limit)  # noqa: E731
    base_plan = plan(deck)
    names = [name for name, _ in base_plan]
    plans = {card: plan(blanked(deck, card)) for card in cards}
    base: list[list] = [[] for _ in names]
    variant = {card: [[] for _ in names] for card in cards}
    budget, spent = (1 + len(cards)) * games * len(names), 0
    active, last, why = list(cards), {}, {}
    for look in range(1, looks + 1):
        lo, hi = (look - 1) * batch, min(most, look * batch)
        cost = (hi - lo) * len(names) * (1 + len(active))
        if look > 1 and spent + cost > budget:
            break  # what is left would pass the games a fixed run plays
        say(f"Round {look} of {looks}: baseline and {len(active)} card{'s' if len(active) != 1 else ''}...")
        for played, new in zip(base, play_plans([(name, tasks[lo:hi]) for name, tasks in base_plan], workers)):
            played += new
        spent += (hi - lo) * len(names)
        for card in list(active):
            for played, new in zip(variant[card], play_plans([(name, tasks[lo:hi]) for name, tasks in plans[card]], workers)):
                played += new
            spent += (hi - lo) * len(names)
            comparison = summarize(*pair_up(base, variant[card], names))
            comparison.z, comparison.target = z, target
            last[card] = comparison
            reason = stop_reason(comparison, most * len(names), look == looks)
            if reason:
                why[card] = reason
                active.remove(card)
        if not active:
            break
    return base, names, last, why, spent, budget, looks, z


def measure_impacts(deck: Deck, opponents: dict[str, Deck], cards: list[str] | None = None, *, top: int = 12, games: int = 40, pod: int = 2,
                    seed: int = 0, max_turns: int = 60, time_limit: float = 120.0, workers: int = 1, goldfish_games: int = 300,
                    goldfish_turns: int = 8, progress: Callable[[str], None] | None = None, early_stop: bool = False,
                    target: float = 0.05) -> ImpactReport:
    """Play the baseline and, for each card, the same games with the card blanked. `cards` names them; by default the `top` that the
    goldfish scores lowest. With `early_stop` the games are played in rounds and a card is dropped once its answer is clear or hopeless
    (see `_in_rounds`); `target` is the impact in score that "hopeless" is judged against."""
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
    comparisons, stops = {}, {}
    spent = budget = 0
    looks, z = 1, Z
    if early_stop and games > 1:
        base, names, comparisons, stops, spent, budget, looks, z = _in_rounds(
            deck, opponents, cards, games, pod, seed, max_turns, time_limit, workers, target, say)
    else:
        plan = lambda d: plan_games(d, opponents, games, pod, seed, max_turns, time_limit)  # noqa: E731
        say("Baseline...")
        base_plan = plan(deck)
        names = [name for name, _ in base_plan]
        base = play_plans(base_plan, workers)
        for i, name in enumerate(cards, 1):
            say(f"{name} ({i}/{len(cards)})...")
            comparisons[name] = summarize(*pair_up(base, play_plans(plan(blanked(deck, name)), workers), names))
    finished = [score(result) for group in base for result in group if result.error is None]
    baseline_score = sum(finished) / len(finished) if finished else 0.0
    impacts = []
    for name in cards:
        comparison = comparisons[name]
        copies = sum(1 for card in deck.main if card.name == name)
        lines = unsupported_lines(in_deck[name])
        differing = comparison.changed_better + comparison.baseline_better
        impacts.append(CardGameImpact(name, copies, comparison.pairs, -comparison.difference, comparison.error, differing, lines[0] if lines else None,
                                      comparison.pairs_needed(0.05) if differing >= MIN_DIFFERING else None, z, stops.get(name)))
    impacts.sort(key=lambda c: (c.impact / c.copies, c.card))
    notes = ["Most pairs come out identical (the 'differ' column): a card is drawn in only a fraction of games, and often changes nothing when it is. "
             "'For 5 pts' is about how many pairs it takes to resolve a 5 point impact at that spread; a dash means fewer than "
             f"{MIN_DIFFERING} pairs differed, too few to estimate it."]
    if budget:
        decided = sum(1 for c in impacts if c.stopped)
        notes.append(f"Stopping rule: {looks} looks, each interval widened to {confidence(z)} so the chance that a card whose true impact is zero looks "
                     f"clear stays under 5% (per card). {decided} of {len(impacts)} cards were settled early ({sum(c.stopped == 'clear' for c in impacts)} clear, "
                     f"{sum(c.stopped == 'hopeless' for c in impacts)} hopeless); {spent} games were played against the {budget} a fixed run plays"
                     + (f", and the cards still undecided used what the others left ({max(c.pairs for c in impacts)} pairs against the {games * len(names)} "
                        "a fixed run plays)." if max(c.pairs for c in impacts) > games * len(names) else "."))
    if len(impacts) > 1:
        notes.append(f"{len(impacts)} cards were tested: about one in twenty would look clear by chance. Re-run the ones you act on with another --seed.")
    unreadable = [c.card for c in impacts if c.unreadable]
    if unreadable:
        notes.append(f"The engine can't fully play {', '.join(unreadable)}: it casts them and ignores the text it can't read, so these games cannot see what that text does.")
    return ImpactReport(games, list(opponents), baseline_score, impacts, notes, spent, budget)


def format_impacts(report: ImpactReport) -> str:
    where = f"against {', '.join(report.opponents)}" if len(report.opponents) <= 3 else f"against {len(report.opponents)} opponents"
    lines = [f"Card impact in real games: {report.games} paired games {where} for each of {len(report.impacts)} cards. The same games are played "
             "with every copy of the card replaced by a blank; the impact is the score the card adds (a win is 1, a draw 1/2), in points.",
             f"The unchanged deck scores {report.baseline_score:.1%}.", "",
             "card                                  copies  impact                       pairs  differ  for 5 pts  note"]
    for c in report.impacts:
        low, high = c.interval
        tag = "" if c.clear else "  (within noise)"
        note = "; ".join(part for part in ((f"stopped early: {c.stopped}" if c.stopped else ""), (f"can't read: {c.unreadable[:40]}" if c.unreadable else "")) if part)
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
    parser.add_argument("opponents", nargs="*", help="decklists to play against (default: the saved gauntlet, see gauntlet.py)")
    parser.add_argument("--cards", action="append", default=None, metavar="CARD", help="a card to measure (repeat for several); default: the weakest by goldfish")
    parser.add_argument("--top", type=int, default=12, help="how many of the goldfish's lowest scores to measure")
    parser.add_argument("--games", type=int, default=40, help="paired games per opponent (in all, with --pod)")
    parser.add_argument("--pod", type=int, default=2, help="players per game; above 2 draws the opponents at random")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--time-limit", type=float, default=120.0, help="seconds per game")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--goldfish-games", type=int, default=300, help="games for choosing the weakest cards")
    parser.add_argument("--early-stop", action="store_true", help="play in rounds, drop a card once its impact is clear or out of reach, and give the games it leaves to the rest")
    parser.add_argument("--target", type=float, default=0.05, help="with --early-stop, the impact in score that decides 'hopeless' (0.05 is five points)")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    source = source or BulkSource(args.bulk)
    name = lambda path: os.path.splitext(os.path.basename(path))[0]  # noqa: E731

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return load_deck(f.read(), source)

    try:
        report = measure_impacts(load(args.decklist), {name(p): load(p) for p in opponent_paths(args.opponents)}, args.cards, top=args.top, games=args.games,
                                 pod=args.pod, seed=args.seed, max_turns=args.max_turns, time_limit=args.time_limit, workers=args.workers,
                                 goldfish_games=args.goldfish_games, progress=lambda m: print(m, file=sys.stderr, flush=True),
                                 early_stop=args.early_stop, target=args.target)
    except (CardNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    print(format_impacts(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
