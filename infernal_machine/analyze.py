"""One report for a deck: the Bracket, the mana base, the goldfish, the tuning report and, with opponents, the matchups.

    python -m infernal_machine.analyze DECKLIST [OPPONENT ...] [--games 40] [--sim-games 500] [--turns 8] [--seed 0]
                                       [--pod 2] [--workers N] [--try "Card Name"]... [--skip tuning,matchups] [--output FILE]

Each part is a tool of its own (`brackets`, `manabase`, `simulate`, `tune`, `matchup`) and keeps its own options and meaning; this
runs them in order with the shared ones given once and prints markdown. The cards the engine can't play come first, since they qualify
everything below them. A Standard deck (no commander) has no Bracket section; with no opponents there is no matchup section. What was
run, and how long each part took, is at the end. Progress goes to stderr so a long run shows it is alive.
"""

from __future__ import annotations

import io
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from .brackets import analyze as bracket_analyze
from .cards import Deck
from .formats import STANDARD, format_of
from .manabase import analyze_mana_base, format_mana_base
from .matchup import format_matchups, matchups
from .report import IN_A_GAME, unplayable_cards, unplayable_note
from .simulate import format_simulation, simulate
from .tune import format_tuning, tune

PARTS = ("bracket", "manabase", "goldfish", "tuning", "matchups")  # the names `skip` takes


@dataclass
class Section:
    title: str
    body: str
    seconds: float = 0.0
    code: bool = True  # a table to keep its alignment: shown in a code block


@dataclass
class Analysis:
    name: str
    kind: str  # "Commander" or "Standard"
    sections: list[Section] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # parts left out, and why

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.sections)


def analyze_deck(deck: Deck, opponents: dict[str, Deck] | None = None, *, name: str = "deck", games: int = 40, sim_games: int = 500,
                 turns: int = 8, seed: int = 0, pod: int = 2, workers: int = 1, candidates: Iterable = (),
                 skip: Iterable[str] = (), progress: Callable[[str], None] | None = None) -> Analysis:
    """Run the parts of the analysis and collect them. `games` is per opponent for the matchups, `sim_games` for the goldfish and the
    tuning report; `skip` names parts (see PARTS) to leave out."""
    left_out = set(skip)
    unknown = left_out - set(PARTS)
    if unknown:
        raise ValueError(f"unknown part(s) to skip: {', '.join(sorted(unknown))} (known: {', '.join(PARTS)})")
    commander = bool(deck.commanders)
    if opponents:
        format_of([deck, *opponents.values()])  # (a table can't mix decks with commanders and decks without)
    analysis = Analysis(name, "Commander" if commander else STANDARD.name.capitalize())
    say = progress or (lambda message: None)

    def run(part: str, title: str, make: Callable[[], str], code: bool = True) -> None:
        if part in left_out:
            analysis.skipped.append(f"{title} (skipped on request)")
            return
        say(f"{title}...")
        started = time.monotonic()
        body = make()
        analysis.sections.append(Section(title, body, time.monotonic() - started, code))

    unplayable = unplayable_cards(deck)
    if unplayable:
        also = " The matchup win rates below are unreliable for the same reason." if opponents and "matchups" not in left_out else ""
        analysis.sections.append(Section("Cards the engine can't play", unplayable_note(unplayable, "The deck", IN_A_GAME + also), 0.0, code=False))
    if commander:
        run("bracket", "Commander Bracket", lambda: _sentence(bracket_analyze(deck).summary()), code=False)
    else:
        analysis.skipped.append("Commander Bracket (a deck with no commander has none)")
    run("manabase", "Mana base", lambda: _mana_base(deck))
    run("goldfish", "Goldfish", lambda: format_simulation(simulate(deck, sim_games, turns, seed)))
    run("tuning", "Tuning", lambda: format_tuning(tune(deck, sim_games, turns, seed, list(candidates)), bracket=False, unplayable=False, mana_base=False))
    if opponents:
        run("matchups", "Matchups", lambda: format_matchups(matchups(deck, opponents, games, pod, seed, workers=workers), name, focus_warning=False))
    else:
        analysis.skipped.append("Matchups (no opponents given)")
    return analysis


def _sentence(text: str) -> str:
    """A capital first letter and a full stop, leaving the rest as it is (`str.capitalize` would lower "Bracket")."""
    return text[:1].upper() + text[1:] + "."


def _mana_base(deck: Deck) -> str:
    base = analyze_mana_base(deck)
    return format_mana_base(base) if base else "This deck has no colored mana symbols."


def format_analysis(analysis: Analysis, settings: str = "") -> str:
    lines = [f"# Analysis of {analysis.name}", "", f"{analysis.kind} deck." + (f" {settings}" if settings else "")]
    for section in analysis.sections:
        lines += ["", f"## {section.title}", ""]
        lines += ["```", section.body, "```"] if section.code else [section.body]
    lines += ["", "---", ""]
    if analysis.skipped:
        lines.append("Left out: " + "; ".join(analysis.skipped) + ".")
    timings = ", ".join(f"{s.title.lower()} {s.seconds:.1f}s" for s in analysis.sections if s.seconds >= 0.05)
    lines.append(f"Took {analysis.seconds:.0f} seconds" + (f" ({timings})" if timings else "") + ".")
    return "\n".join(lines)


def main(argv: list[str], source=None) -> int:
    import argparse
    import os

    from .cards import BulkSource, CardNotFound, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("opponents", nargs="*", help="decklists to play matchups against")
    parser.add_argument("--games", type=int, default=40, help="matchup games per opponent (in all, with --pod)")
    parser.add_argument("--sim-games", type=int, default=500, help="games for the goldfish and the tuning report")
    parser.add_argument("--turns", type=int, default=8, help="turns of the goldfish and the tuning report")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pod", type=int, default=2, help="players per matchup game; above 2 draws the opponents at random")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--try", dest="candidates", action="append", default=[], metavar="CARD", help="a card to test in the weakest slot")
    parser.add_argument("--skip", default="", help=f"parts to leave out, comma separated: {', '.join(PARTS)}")
    parser.add_argument("--output", metavar="FILE", help="write the report here as well as printing it")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    source = source or BulkSource(args.bulk)
    name = lambda path: os.path.splitext(os.path.basename(path))[0]  # noqa: E731

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return load_deck(f.read(), source)

    try:
        deck = load(args.decklist)
        opponents = {name(p): load(p) for p in args.opponents}
        candidates = [source.get(card) for card in args.candidates]
        analysis = analyze_deck(deck, opponents, name=name(args.decklist), games=args.games, sim_games=args.sim_games, turns=args.turns,
                                seed=args.seed, pod=args.pod, workers=args.workers, candidates=candidates,
                                skip=[part for part in args.skip.split(",") if part], progress=lambda m: print(m, file=sys.stderr, flush=True))
    except (CardNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    settings = f"Goldfish and tuning: {args.sim_games} games, {args.turns} turns; matchups: {args.games} games per opponent; seed {args.seed}."
    report = format_analysis(analysis, settings)
    print(report)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
