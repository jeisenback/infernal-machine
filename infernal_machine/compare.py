"""Compare two builds of a deck head to head.

    python -m infernal_machine.compare BASELINE CHANGED OPPONENT [OPPONENT ...] [--games N] [--pod N] [--workers N]

Both builds play the same games: game `n` against an opponent has the same seed, seat and opponents whichever build is playing
(`matchup.plan_games`), so a pair of games differs only by the cards that changed. The result is the difference in score (a win
is 1, a draw 1/2) over the pairs, with a 95% interval from the spread of the per-pair differences. That is far less noisy than
comparing two separate win rates, and it shows how many pairs it takes to separate a difference of a given size. A pair is dropped
if either game crashes or times out. The goldfish metrics of the two builds (`simulate`) are printed side by side.

The bots play every game, so the difference is how the *bots* do with the two builds; a card they play badly (a combo piece, a
card that wants careful play) is under-rated in both. Cards the engine can't read are named when they are among the ones that
changed, since the comparison cannot see what they do.

With `--early-stop` the games are played in up to ten rounds and the comparison stops when it is settled: when the interval of the
difference leaves out zero ("clear"), or when the pairs it would take to separate a 5 point difference are more than three times
the pairs planned ("hopeless": more games would not settle it either). Looking after every round and stopping the first time the
interval excludes zero would call identical builds "clear" far more than one time in twenty, so each look uses an interval widened
for the number of looks (a Bonferroni bound: the chance that any look is falsely clear is at most 5%).
"""

from __future__ import annotations

import io
import math
import sys
from collections import Counter
from dataclasses import dataclass, field

from .brackets import analyze as bracket_analyze
from .cards import Deck
from .formats import format_of
from .gauntlet import opponent_paths
from .matchup import GameResult, play_plans, plan_games
from .report import unplayable_cards
from .sequential import HOPELESS_FACTOR, MAX_LOOKS, MIN_DIFFERING, MIN_LOOK_PAIRS, Z, confidence, look_z, schedule  # noqa: F401
from .simulate import SimStats, simulate



@dataclass
class OpponentLine:
    opponent: str
    pairs: int
    baseline: float  # mean score of the baseline build over these pairs
    changed: float
    difference: float  # changed minus baseline


@dataclass
class Comparison:
    pairs: int  # games both builds finished
    dropped: int  # pairs lost because a game of the pair crashed or timed out
    baseline_score: float
    changed_score: float
    difference: float  # mean per-pair score difference, changed minus baseline
    error: float  # its standard error
    spread: float  # the standard deviation of the per-pair differences
    changed_better: int  # pairs the changed build scored higher in
    baseline_better: int
    same: int
    opponents: list[OpponentLine] = field(default_factory=list)
    removed: dict[str, int] = field(default_factory=dict)  # cards the changed build has fewer of, and by how many
    added: dict[str, int] = field(default_factory=dict)
    goldfish: tuple[SimStats, SimStats] | None = None  # (baseline, changed)
    notes: list[str] = field(default_factory=list)
    z: float = Z  # the interval's width in standard errors (wider than Z when the comparison looked repeatedly)
    planned: int = 0  # pairs an early-stopping comparison planned to play (0: it was not early-stopping)
    looks: int = 1  # how many times it could look at the result
    batch: int = 0  # games per opponent between looks
    stopped: str | None = None  # "clear" or "hopeless" if it stopped before playing every planned pair
    target: float = 0.05  # the difference "hopeless" is judged against

    @property
    def confidence(self) -> str:
        return confidence(self.z)

    @property
    def interval(self) -> tuple[float, float]:
        return self.difference - self.z * self.error, self.difference + self.z * self.error

    @property
    def clear(self) -> bool:
        """Whether the 95% interval of the difference leaves out zero."""
        low, high = self.interval
        return low > 0 or high < 0

    def pairs_needed(self, size: float) -> int | None:
        """About how many pairs it takes for a true difference of `size` (in score, 0.05 is five points) to clear zero at this spread.
        None if no pair differed, since then the spread says nothing."""
        return math.ceil((Z * self.spread / size) ** 2) if self.spread > 0 else None


def stop_reason(c: Comparison, planned: int, final: bool) -> str | None:
    """Whether a comparison can stop now: "clear" (the interval excludes zero) or "hopeless" (more pairs than `HOPELESS_FACTOR` times
    those planned are needed to separate `c.target`), or None. Neither is said before `MIN_LOOK_PAIRS` pairs, when the spread (and
    with a few alike pairs, an interval of no width) says too little, and the last look never stops early."""
    if final or c.pairs < MIN_LOOK_PAIRS:
        return None
    if c.clear:
        return "clear"
    needed = c.pairs_needed(c.target)
    if c.changed_better + c.baseline_better >= MIN_DIFFERING and needed and needed > HOPELESS_FACTOR * planned:
        return "hopeless"
    return None


def score(result: GameResult) -> float:
    """1 for a win by the deck being tested, 1/2 for a draw, 0 for a loss."""
    return 1.0 if result.winner == result.focus_seat else 0.5 if result.winner is None else 0.0


def deck_diff(baseline: Deck, changed: Deck) -> tuple[dict[str, int], dict[str, int]]:
    """(removed, added): the cards the changed build has fewer and more of, commanders and main deck together."""
    before = Counter(c.name for c in baseline.commanders + baseline.main)
    after = Counter(c.name for c in changed.commanders + changed.main)
    return ({name: n for name, n in sorted((before - after).items())}, {name: n for name, n in sorted((after - before).items())})


def pair_up(baseline: list[list[GameResult]], changed: list[list[GameResult]], names: list[str]) -> tuple[list[float], list[OpponentLine], int]:
    """(per-pair differences, a line per opponent, dropped pairs) from the two builds' results, planned with the same seed."""
    differences: list[float] = []
    lines = []
    dropped = 0
    for name, before, after in zip(names, baseline, changed):
        pairs = [(score(a), score(b)) for a, b in zip(before, after) if a.error is None and b.error is None]
        dropped += len(before) - len(pairs)
        differences += [b - a for a, b in pairs]
        if pairs:
            lines.append(OpponentLine(name, len(pairs), sum(a for a, _ in pairs) / len(pairs), sum(b for _, b in pairs) / len(pairs),
                                      sum(b - a for a, b in pairs) / len(pairs)))
    return differences, lines, dropped


def summarize(differences: list[float], lines: list[OpponentLine], dropped: int) -> Comparison:
    n = len(differences)
    mean = sum(differences) / n if n else 0.0
    spread = math.sqrt(sum((d - mean) ** 2 for d in differences) / (n - 1)) if n > 1 else 0.0
    weighted = lambda pick: sum(pick(line) * line.pairs for line in lines) / n if n else 0.0  # noqa: E731
    return Comparison(n, dropped, weighted(lambda line: line.baseline), weighted(lambda line: line.changed), mean,
                      spread / math.sqrt(n) if n else 0.0, spread, sum(d > 0 for d in differences), sum(d < 0 for d in differences),
                      sum(d == 0 for d in differences), lines)


def compare_builds(baseline: Deck, changed: Deck, opponents: dict[str, Deck], games: int = 40, pod: int = 2, seed: int = 0,
                   max_turns: int = 60, time_limit: float = 120.0, workers: int = 1, goldfish_games: int = 0, goldfish_turns: int = 8,
                   early_stop: bool = False, target: float = 0.05) -> Comparison:
    """Play `games` paired games per opponent (or in all, for a pod) with each build and compare. With `goldfish_games`, also run
    `simulate` on both. With `early_stop`, play them in rounds and stop when the answer is clear or hopeless (see the module docstring);
    `target` is the difference in score "hopeless" is judged against."""
    format_of([baseline, changed])  # (a table can't mix decks with commanders and decks without)
    plans = [plan_games(deck, opponents, games, pod, seed, max_turns, time_limit) for deck in (baseline, changed)]
    names = [name for name, _ in plans[0]]
    if early_stop and games > 1:
        comparison = _play_in_rounds(plans, names, games, workers, target)
    else:
        results = [play_plans(plan, workers) for plan in plans]
        comparison = summarize(*pair_up(results[0], results[1], names))
    comparison.removed, comparison.added = deck_diff(baseline, changed)
    if goldfish_games:
        comparison.goldfish = (simulate(baseline, goldfish_games, goldfish_turns, seed), simulate(changed, goldfish_games, goldfish_turns, seed))
    comparison.notes = _notes(baseline, changed, comparison)
    return comparison


def _play_in_rounds(plans: list, names: list[str], games: int, workers: int, target: float) -> Comparison:
    """Play the planned games a round at a time (game `n` is the same wherever it is played, so the pairs do not change) and look after
    each round; see `stop_reason`."""
    looks, batch = schedule(games)
    z, planned = look_z(looks), games * len(names)
    results: list[list[list[GameResult]]] = [[[] for _ in names] for _ in plans]
    comparison = summarize([], [], 0)
    for look in range(1, looks + 1):
        lo, hi = (look - 1) * batch, min(games, look * batch)
        for build, plan in zip(results, plans):
            for played, new in zip(build, play_plans([(name, tasks[lo:hi]) for name, tasks in plan], workers)):
                played += new
        comparison = summarize(*pair_up(results[0], results[1], names))
        comparison.z, comparison.planned, comparison.looks, comparison.batch, comparison.target = z, planned, looks, batch, target
        comparison.stopped = stop_reason(comparison, planned, look == looks)
        if comparison.stopped:
            break
    return comparison


def _notes(baseline: Deck, changed: Deck, comparison: Comparison) -> list[str]:
    notes = []
    if len(baseline.main) != len(changed.main):
        notes.append(f"The builds have {len(baseline.main)} and {len(changed.main)} cards, so they shuffle differently and the games pair less closely.")
    if baseline.commanders and changed.commanders:
        before, after = bracket_analyze(baseline).floor, bracket_analyze(changed).floor
        if before != after:
            notes.append(f"Bracket: the baseline plays at Bracket {before} or higher, the changed build at {after} or higher.")
    unreadable = {name for name, _, _ in unplayable_cards(baseline)} | {name for name, _, _ in unplayable_cards(changed)}
    touched = sorted(unreadable & (set(comparison.removed) | set(comparison.added)))
    if touched:
        notes.append(f"The engine can't fully play {', '.join(touched)}, which changed: it casts the card and ignores the text it can't read, "
                     "so this comparison cannot see what that text does.")
    if comparison.dropped:
        notes.append(f"{comparison.dropped} pair(s) were dropped because a game crashed or timed out.")
    return notes


def format_comparison(c: Comparison, baseline: str = "baseline", changed: str = "changed") -> str:
    if not c.pairs:
        return "No pair finished, so there is nothing to compare." + "".join(f"\n{note}" for note in c.notes)
    changes = ", ".join([f"-{n} {name}" for name, n in c.removed.items()] + [f"+{n} {name}" for name, n in c.added.items()]) or "no card differs"
    low, high = c.interval
    verdict = ("the changed build is better" if c.difference > 0 else "the baseline is better") if c.clear else "within noise: more pairs are needed"
    if c.stopped == "hopeless":
        verdict = "within noise, and more pairs would not settle it"
    lines = [f"{c.pairs} paired games. {baseline} against {changed}: {changes}.", "",
             f"Score (a win is 1, a draw 1/2): {baseline} {c.baseline_score:.1%}, {changed} {c.changed_score:.1%}.",
             f"Difference {c.difference * 100:+.1f} points ({c.confidence} interval {low * 100:+.1f} to {high * 100:+.1f}): {verdict}.",
             f"Pairs: {changed} did better in {c.changed_better}, {baseline} did better in {c.baseline_better}, the same in {c.same}."]
    if c.planned:
        rule = (f"Stopping rule: {c.looks} looks, one per {c.batch} games per opponent; each look's interval is widened to {c.confidence} so the "
                f"chance of a false \"clear\" on equal builds stays under 5%.")
        if c.stopped == "clear":
            lines.append(f"Stopped early: clearly {'better' if c.difference > 0 else 'worse'} after {c.pairs} of {c.planned} planned pairs. {rule}")
        elif c.stopped == "hopeless":
            lines.append(f"Stopped early: within noise after {c.pairs} of {c.planned} planned pairs; about {c.pairs_needed(c.target)} pairs would be "
                         f"needed to separate a {c.target * 100:g} point difference, more than {HOPELESS_FACTOR} times the plan. {rule}")
        else:
            lines.append(f"Played all {c.planned} planned pairs; neither stop applied. {rule}")
    needed = {size: c.pairs_needed(size) for size in (0.05, 0.10)}
    if all(needed.values()):
        lines.append(f"At this spread, about {needed[0.10]} pairs separate a 10 point difference from nothing, and about {needed[0.05]} a 5 point one.")
    elif c.spread == 0:
        lines.append("No pair came out differently, so the games say nothing about how many pairs it would take.")
    if len(c.opponents) > 1:
        lines += ["", "opponent                       pairs  baseline  changed  difference"]
        lines += [f"{o.opponent[:30]:<30} {o.pairs:>5}  {o.baseline:>8.1%}  {o.changed:>7.1%}  {o.difference * 100:>+8.1f}" for o in c.opponents]
    if c.goldfish:
        before, after = c.goldfish
        rows = [("mulligan rate", f"{before.mulligan_rate:.1%}", f"{after.mulligan_rate:.1%}"),
                ("opening lands", f"{before.average_opening_lands}", f"{after.average_opening_lands}"),
                ("mana spent / available", f"{before.mana_efficiency:.0%}", f"{after.mana_efficiency:.0%}"),
                ("on curve", _percent(before.on_curve), _percent(after.on_curve)),
                (f"land drops through turn {before.turns // 2}", f"{before.land_drop_rate[before.turns // 2]:.1%}", f"{after.land_drop_rate[after.turns // 2]:.1%}"),
                (f"damage by turn {before.turns}", f"{before.damage[before.turns]:.1f}", f"{after.damage[after.turns]:.1f}")]
        width = max(len(baseline), len(changed), 8)
        lines += ["", f"Goldfish ({before.games} games, {before.turns} turns):", f"{'':<28}{baseline:>{width}}  {changed:>{width}}"]
        lines += [f"{name:<28}{a:>{width}}  {b:>{width}}" for name, a, b in rows]
    lines += ["", *c.notes] if c.notes else []
    return "\n".join(lines)


def _percent(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "-"


def main(argv: list[str]) -> int:
    import argparse
    import os

    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("baseline", help="the decklist being changed")
    parser.add_argument("changed", help="the decklist with the changes")
    parser.add_argument("opponents", nargs="*", help="decklists to play against (default: the saved gauntlet, see gauntlet.py)")
    parser.add_argument("--games", type=int, default=40, help="paired games per opponent (in all, with --pod)")
    parser.add_argument("--pod", type=int, default=2, help="players per game; above 2 draws the opponents at random")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=60)
    parser.add_argument("--time-limit", type=float, default=120.0, help="seconds per game")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--goldfish-games", type=int, default=500, help="games for the goldfish side by side (0 to skip)")
    parser.add_argument("--turns", type=int, default=8, help="turns of the goldfish")
    parser.add_argument("--early-stop", action="store_true", help="play in rounds and stop when the answer is clear or hopeless")
    parser.add_argument("--target", type=float, default=0.05, help="with --early-stop, the difference in score that decides 'hopeless' (0.05 is five points)")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    source = BulkSource(args.bulk)

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return load_deck(f.read(), source)

    name = lambda path: os.path.splitext(os.path.basename(path))[0]  # noqa: E731
    opponents = {name(p): load(p) for p in opponent_paths(args.opponents)}
    comparison = compare_builds(load(args.baseline), load(args.changed), opponents, args.games, args.pod, args.seed, args.max_turns,
                                args.time_limit, args.workers, args.goldfish_games, args.turns, args.early_stop, args.target)
    print(format_comparison(comparison, name(args.baseline), name(args.changed)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
