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

from . import history
from .brackets import analyze as bracket_analyze
from .cards import Deck
from .formats import add_format_argument, format_of, with_format
from .gauntlet import deck_format, opponent_paths
from .manabase import analyze_mana_base, format_mana_base
from .matchup import format_matchups, matchups
from .coverage import FIXES_SHOWN, playability, verdict
from .report import IN_A_GAME, unplayable_note
from .simulate import format_simulation, simulate
from .tune import format_tuning, tune

PARTS = ("playability", "bracket", "manabase", "goldfish", "tuning", "matchups")  # the names `skip` takes


@dataclass
class Section:
    title: str
    body: str
    seconds: float = 0.0
    code: bool = True  # a table to keep its alignment: shown in a code block
    part: str = ""  # which of PARTS it is ("" for the note about unplayable cards)
    data: dict = field(default_factory=dict)  # the part's numbers, as JSON keeps them (see history.py)


@dataclass
class Analysis:
    name: str
    kind: str  # "Commander" or "Standard"
    sections: list[Section] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # parts left out, and why
    reused: list[str] = field(default_factory=list)  # parts taken from an earlier run (same deck and settings) instead of played again
    changes: str = ""  # what moved against that run, when one was given
    record: dict = field(default_factory=dict)  # this run as `history.snapshot` keeps it

    @property
    def seconds(self) -> float:
        return sum(s.seconds for s in self.sections)


def _known_parts(skip: Iterable[str]) -> set[str]:
    left_out = set(skip)
    unknown = left_out - set(PARTS)
    if unknown:
        raise ValueError(f"unknown part(s) to skip: {', '.join(sorted(unknown))} (known: {', '.join(PARTS)})")
    return left_out


def analyze_deck(deck: Deck, opponents: dict[str, Deck] | None = None, *, name: str = "deck", games: int = 40, sim_games: int = 500,
                 turns: int = 8, seed: int = 0, pod: int = 2, workers: int = 1, candidates: Iterable = (),
                 skip: Iterable[str] = (), progress: Callable[[str], None] | None = None, since: dict | None = None, reuse: bool = True,
                 since_name: str = "the earlier run") -> Analysis:
    """Run the parts of the analysis and collect them. `games` is per opponent for the matchups, `sim_games` for the goldfish and the
    tuning report; `skip` names parts (see PARTS) to leave out. `since` is an earlier run (`history.load`): what moved against it is in
    `changes`, and a part it has for the same deck and settings is reused unless `reuse` is false."""
    left_out = _known_parts(skip)
    candidates = list(candidates)
    settings = {"games": games, "sim_games": sim_games, "turns": turns, "seed": seed, "pod": pod, "candidates": [getattr(c, "name", str(c)) for c in candidates]}
    fmt = format_of([deck, *(opponents or {}).values()])  # (a table can't mix formats, or decks with commanders and decks without)
    commander = fmt.name == "commander"  # the Brackets are Commander's
    analysis = Analysis(name, fmt.label)
    say = progress or (lambda message: None)

    reused_parts: list[str] = []

    def run(part: str, title: str, make: Callable[[], tuple[str, dict]], code: bool = True) -> None:
        if part in left_out:
            analysis.skipped.append(f"{title} (skipped on request)")
            return
        saved = history.reusable(since if reuse else None, part, deck, settings, opponents)
        if saved:
            say(f"{title} (reused from {since_name})")
            analysis.sections.append(Section(title, saved["body"], 0.0, saved["code"], part, saved["data"]))
            analysis.reused.append(title.lower())
            reused_parts.append(part)
            return
        say(f"{title}...")
        started = time.monotonic()
        body, data = make()
        analysis.sections.append(Section(title, body, time.monotonic() - started, code, part, history.jsonable(data)))

    # Never reused from an earlier run: what the engine can play changes with the engine, not with the deck or the settings.
    if "playability" in left_out:
        analysis.skipped.append("Playability (skipped on request)")
    else:
        started = time.monotonic()
        also = " The matchup win rates below are unreliable for the same reason." if opponents and "matchups" not in left_out else ""
        body, data = _playability(deck, name, also)
        analysis.sections.append(Section("Playability", body, time.monotonic() - started, False, "playability", history.jsonable(data)))
    if commander:
        run("bracket", "Commander Bracket", lambda: _bracket(deck), code=False)
    else:
        analysis.skipped.append(f"Commander Bracket ({'a deck with no commander has none' if not deck.commanders else 'Brackets are for Commander decks, not ' + fmt.label})")
    run("manabase", "Mana base", lambda: _mana_base(deck))
    run("goldfish", "Goldfish", lambda: _goldfish(deck, sim_games, turns, seed))
    run("tuning", "Tuning", lambda: _tuning(deck, sim_games, turns, seed, candidates))
    if opponents:
        run("matchups", "Matchups", lambda: _matchups(deck, opponents, games, pod, seed, workers, name))
    else:
        analysis.skipped.append("Matchups (no opponents given)")
    analysis.record = history.snapshot(name, deck, settings, {s.part: {"title": s.title, "body": s.body, "code": s.code, "data": s.data}
                                                              for s in analysis.sections if s.part}, opponents)
    analysis.record["reused"] = reused_parts
    if since:
        analysis.changes = history.compare(since, analysis.record, since_name)
    return analysis


def _short(line: str, limit: int = 160) -> str:
    """A rules-text line for one row of the printed report: long ones are cut (the saved numbers and the HTML keep the whole line)."""
    return line if len(line) <= limit else line[:limit - 3].rstrip() + "..."


def _playability(deck: Deck, name: str, also: str = "") -> tuple[str, dict]:
    """The verdict on the deck (issue #477): whether the engine plays every card, which it can't and the lines to build to unlock them."""
    data = playability(deck, name)
    cards, playable = data["cards"], data["playable"]
    if not cards:
        return "The deck has no cards.", data
    share = f"{playable} of {cards} cards fully playable ({playable / cards:.0%})"
    if playable == cards:
        return f"{verdict(0)}: {share}. Every card is one the engine understands.", data
    blocked = [(c["name"], c["copies"], c["line"]) for c in data["unplayable"]]
    lines = [f"{verdict(cards - playable)}: {share}.", "", unplayable_note(blocked, "The deck", IN_A_GAME + also)]
    fixes = data["fixes"]
    if fixes:
        lines += ["", "Fix these lines to unlock this deck:"]
        for i, fix in enumerate(fixes[:FIXES_SHOWN], 1):
            more = fix["unlocks"] - len(fix["cards"])
            who = ", ".join(fix["cards"]) + (f" and {more} more" if more > 0 else "")
            lines.append(f"{i}. {_short(fix['line'])} (unlocks {fix['unlocks']}: {who}) -> {fix['playable_after']:.0%} playable")
        if len(fixes) > FIXES_SHOWN:
            lines.append(f"... and {len(fixes) - FIXES_SHOWN} more pieces of work that each unlock at least one card.")
    return "\n".join(lines), data


def _sentence(text: str) -> str:
    """A capital first letter and a full stop, leaving the rest as it is (`str.capitalize` would lower "Bracket")."""
    return text[:1].upper() + text[1:] + "."


def _bracket(deck: Deck) -> tuple[str, dict]:
    report = bracket_analyze(deck)
    return _sentence(report.summary()), {"floor": report.floor, "game_changers": sorted(report.game_changers)}


def _mana_base(deck: Deck) -> tuple[str, dict]:
    base = analyze_mana_base(deck)
    if not base:
        return "This deck has no colored mana symbols.", {}
    return format_mana_base(base), {"lands": base.lands, "colors": {line.color: {"have": line.have, "needed": line.needed, "short": line.short}
                                                                    for line in base.colors}}


def _goldfish(deck: Deck, games: int, turns: int, seed: int) -> tuple[str, dict]:
    stats = simulate(deck, games, turns, seed)
    return format_simulation(stats), {"games": stats.games, "turns": stats.turns, "mulligan_rate": stats.mulligan_rate,
                                      "opening_lands": stats.average_opening_lands, "mana_efficiency": stats.mana_efficiency, "on_curve": stats.on_curve,
                                      "land_drops": stats.land_drop_rate, "damage": stats.damage}


def _tuning(deck: Deck, games: int, turns: int, seed: int, candidates: list) -> tuple[str, dict]:
    report = tune(deck, games, turns, seed, candidates)
    data = {"games": report.games, "turns": report.turns, "baseline": report.baseline,  # (what the HTML report draws; see htmlreport.py)
            "cards": [{"name": c.name, "copies": c.copies, "delta": c.value.delta, "error": c.value.error, "seen": c.seen_rate,
                       "cast_when_seen": c.cast_when_seen, "note": c.note} for c in report.cards],
            "lands": {k: {"delta": e.delta, "error": e.error} for k, e in report.lands.items()},
            "swaps": [{"card": new, "replaces": old, "delta": e.delta, "error": e.error, "note": report.swap_notes.get(new, "")}
                      for new, old, e in report.swaps]}
    return format_tuning(report, bracket=False, unplayable=False, mana_base=False), data


def _matchups(deck: Deck, opponents: dict[str, Deck], games: int, pod: int, seed: int, workers: int, name: str) -> tuple[str, dict]:
    records = matchups(deck, opponents, games, pod, seed, workers=workers)
    return format_matchups(records, name, focus_warning=False), {"pod": pod, "opponents": {r.opponent: {"wins": r.wins, "games": r.games, "draws": r.draws} for r in records}}


def format_analysis(analysis: Analysis, settings: str = "") -> str:
    lines = [f"# Analysis of {analysis.name}", "", f"{analysis.kind} deck." + (f" {settings}" if settings else "")]
    if analysis.changes:
        lines += ["", "## What changed", "", "```", analysis.changes, "```"]
    for section in analysis.sections:
        lines += ["", f"## {section.title}", ""]
        lines += ["```", section.body, "```"] if section.code else [section.body]
    lines += ["", "---", ""]
    if analysis.skipped:
        lines.append("Left out: " + "; ".join(analysis.skipped) + ".")
    if analysis.reused:
        lines.append(history.parts_reused(analysis.reused))
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
    parser.add_argument("opponents", nargs="*", help="decklists to play matchups against (default: the saved gauntlet, see gauntlet.py)")
    parser.add_argument("--games", type=int, default=40, help="matchup games per opponent (in all, with --pod)")
    parser.add_argument("--sim-games", type=int, default=500, help="games for the goldfish and the tuning report")
    parser.add_argument("--turns", type=int, default=8, help="turns of the goldfish and the tuning report")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pod", type=int, default=2, help="players per matchup game; above 2 draws the opponents at random")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--try", dest="candidates", action="append", default=[], metavar="CARD", help="a card to test in the weakest slot")
    parser.add_argument("--skip", default="", help=f"parts to leave out, comma separated: {', '.join(PARTS)}")
    parser.add_argument("--output", metavar="FILE", help="write the report here as well as printing it")
    parser.add_argument("--html", metavar="FILE", help="also write the report as one HTML page: bars, charts and sortable tables, no network")
    parser.add_argument("--save", metavar="FILE", help="keep this run's numbers (a JSON) so a later run can say what changed")
    parser.add_argument("--since", metavar="FILE", help="an earlier run saved with --save: say what moved against it, and reuse its parts that are unchanged")
    parser.add_argument("--no-reuse", action="store_true", help="with --since, play every part again instead of reusing the unchanged ones")
    add_format_argument(parser)
    parser.add_argument("--max-bracket", type=int, metavar="N", help="with no opponents named, only the saved gauntlet decks playable at Bracket N or lower")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    source = source or BulkSource(args.bulk)
    name = lambda path: os.path.splitext(os.path.basename(path))[0]  # noqa: E731

    def load(path: str) -> Deck:
        with open(path, encoding="utf-8") as f:
            return with_format(load_deck(f.read(), source), args.format)

    try:
        deck = load(args.decklist)
        skipped = [part for part in args.skip.split(",") if part]
        _known_parts(skipped)  # (before any opponent is chosen or loaded)
        wanted = args.opponents if args.opponents or "matchups" in skipped else opponent_paths([], args.max_bracket, format=deck_format(deck))
        opponents = {name(p): load(p) for p in wanted}
        candidates = [source.get(card) for card in args.candidates]
        earlier = history.load(args.since) if args.since else None
        analysis = analyze_deck(deck, opponents, name=name(args.decklist), games=args.games, sim_games=args.sim_games, turns=args.turns,
                                seed=args.seed, pod=args.pod, workers=args.workers, candidates=candidates,
                                skip=skipped, progress=lambda m: print(m, file=sys.stderr, flush=True), since=earlier,
                                reuse=not args.no_reuse, since_name=args.since or "the earlier run")
    except (CardNotFound, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    settings = f"Goldfish and tuning: {args.sim_games} games, {args.turns} turns; matchups: {args.games} games per opponent; seed {args.seed}."
    report = format_analysis(analysis, settings)
    print(report)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    if args.html:
        from .htmlreport import render_html

        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render_html(analysis, settings))
        print(f"Wrote the HTML report to {args.html}.", file=sys.stderr)
    if args.save:
        history.save(args.save, analysis.record)
        print(f"Saved this run's numbers to {args.save}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
