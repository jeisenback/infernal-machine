"""How much of the Commander card pool the engine understands, weighted by how much each card is played (the coverage audit,
issue #219).

    python tools/coverage_audit.py [--format commander] [--pool .cache/commander_pool.json] [--top 40] [--json OUT.json]

Fetches every Commander-legal paper card from Scryfall's search API (about 185 pages, a few minutes; the result is kept in
`--pool` and reused for a week), runs the report's `unsupported_lines` over each card, and prints a markdown summary: the share
of fully playable cards overall, by card type and by EDHREC rank (Scryfall carries it), the unsupported lines that appear on the
most cards, and those that are a card's only gap (the cheapest wins). "Fully playable" means the engine understands every line,
not that the card behaves correctly.

    python tools/coverage_audit.py --mechanisms          # also group the gaps by mechanism, ranked by popularity
    python tools/coverage_audit.py --mechanism "Copy"    # the wordings inside one mechanism or family (a substring of its name)
    python tools/coverage_audit.py --next                # the best things to build next, in order
    python tools/coverage_audit.py --decks DECK [DECK ...]   # what blocks these decks, and what to build to play them (offline)

A mechanism is a keyword or ability word at the start of an unsupported line, or else the first of the `MECHANISMS` patterns that
matches it; the patterns are a heuristic, so the groups are a guide to what to build next, not exact counts. "All cards" counts every card with a line in the mechanism, playable or not, so a row shows how much of it is covered. A card's "only gap"
mechanism is the one that holds all its unsupported lines, so building it alone could make the card playable. The tables are sorted
by the only-gap cards in the top `POPULAR` of EDHREC rank.

`--next` ranks pieces of work. A family is a keyword or ability word, or one of the `FAMILIES` patterns (a wording that repeats
across cards and would be built once); add a family when a `--mechanism` drill-down shows one. Each unplayable card needs the
families of its unsupported lines, and a card with a line no family covers is never counted as unlocked. The ranking is greedy:
it picks the family that unlocks the most weighted cards, assumes it built, and repeats. A card that needs two families shares its
weight between them while neither is built, so a pair that unlocks nothing alone can still be suggested. A card weighs
`1 / (1 + rank / WEIGHT_KNEE)` (no rank, no weight), so rank 100 counts for far more than rank 4,900. The result is an estimate: a
family's wordings can still differ from one another, and a card the engine reads is not always a card it plays correctly.

`--decks` is the same question asked of real decklists instead of a modelled deck: every copy of every card counts, the pool is not
fetched (it reads the card file, so it works offline), and the ranking is the greedy one over the pieces of work the decks need. A line
that no `FAMILIES` pattern covers is its own piece of work, named by its wording, so no card is left out as "blocked". It says how many
cards each deck can play, which cards it can't and why, and what to build to play the most of them.

The ranking and the headline are about *decks*, since a deck is what gets simulated (issue #391). A typical deck is modelled by an
inclusion probability for each ranked card, `min(1, scale * weight(rank) ** DECK_TAIL)`, with the scale chosen so that the probabilities
add up to the deck's nonbasic slots (`DECK_CARDS` less `DECK_BASICS`, which are always playable). Then the expected share of a deck
the engine can play is the sum of the probabilities of the playable cards (and the basics) over `DECK_CARDS`, the chance that a whole
deck is playable is the product of the playable chances, and a family's worth is the probabilities of the cards it unlocks: the
cards per deck it makes playable. Squaring the weight makes the tail fall off faster than the one-card weight does (a deck holds
about 28 cards from the top 500, 42 from the top 1000 and 70 from the top 5000, which is a guess at the shape of a real deck, not a
measurement). The model is an assumption, not data (Scryfall carries a rank, not an inclusion rate), so read the share as a number to
track week by week, not as a forecast.
"""

from __future__ import annotations

import argparse
import collections
import functools
import io
import json
import math
import os
import re
import sys
import time
from typing import Any
import urllib.parse
import urllib.request

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import Card  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402
from infernal_machine.coverage import (  # noqa: E402
    MECHANISMS,
    POPULAR,
    analyze,
    analyze_decks,
    baseline_of,
    compare_baseline,
    deck_share,
)

SEARCH = "legal:{format} game:paper -t:token -is:funny"  # Scryfall's search for the cards legal in a format


def fetch_pool(path: str, max_age_days: float = 7.0, pause: float = 0.11, format: str = "commander") -> list[dict]:
    """The paper cards legal in `format` as Scryfall's JSON, from `path` if it is fresh, else from the search API."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        with open(path) as f:
            return json.load(f)
    url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": SEARCH.format(format=format), "unique": "cards"})
    cards: list[dict] = []
    while url:
        request = urllib.request.Request(url, headers={"User-Agent": "infernal-machine/0.1", "Accept": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=90) as response:
                    page = json.load(response)
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
        cards += page["data"]
        url = page.get("next_page")
        time.sleep(pause)  # Scryfall asks for at most ten requests a second
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(cards, f)
    return cards


def render(result: dict, top: int = 40, format: str = "commander") -> str:
    total, playable = result["total"], result["playable"]
    out = [f"## Coverage audit: {playable} of {total} {format.capitalize()}-legal cards fully playable ({100 * playable / total:.1f}%)", ""]
    out.append("| Card type | Fully playable |\n|---|---|")
    for kind, (count, ok) in sorted(result["by_type"].items(), key=lambda kv: -kv[1][0]):
        out.append(f"| {kind} | {ok} of {count} ({100 * ok / count:.0f}%) |")
    if result.get("popularity", True):
        out += ["", "| Most played (EDHREC rank) | Fully playable |\n|---|---|"]
        for n, (ok, of) in result["popular"].items():
            out.append(f"| top {n} | {ok} of {of} ({100 * ok / of:.0f}%) |" if of else f"| top {n} | no ranked cards |")
        deck = result["deck"]
        out += ["", f"A typical {deck['cards'] + 1}-card deck ({deck['basics']} basic lands, the rest chosen by how played each card is) is "
                    f"{deck['share']:.1%} fully playable: about {deck['unplayable']:.1f} of its cards the engine cannot play, and a "
                    f"{deck['clean']:.1%} chance that every one of them is playable."]
    else:
        out += ["", f"There is no play data for {format.capitalize()}, so every card counts the same: the tables below are counts of cards, and "
                    f"the tracked decks (when there are some) say which gaps matter."]
    gaps = len(result["shapes"])
    singles = sum(1 for names in result["shapes"].values() if len(names) == 1)
    out += ["", f"{result['one_gap']} cards have exactly one unsupported line. There are {gaps} distinct unsupported lines, "
                f"{singles} of them on a single card.", ""]
    rank = result["best_rank"]

    def table(title: str, groups: dict[str, list[str]]) -> None:
        out.append(f"### {title}\n\n| Cards | Unsupported line | {'Most played' if result.get('popularity', True) else 'Some of the cards'} |\n|---|---|---|")
        for line, names in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:top]:
            best = ", ".join(f"{n} #{rank[n]}" if n in rank else n for n in names[:2])
            out.append(f"| {len(names)} | `{line.replace('|', '/')}` | {best} |")
        out.append("")

    table("Unsupported lines on the most cards", result["shapes"])
    table("Lines that are a card's only gap", result["only_gap"])
    if result["crashes"]:
        out += ["### Cards the report could not read", ""] + [f"- {c}" for c in result["crashes"][:20]] + [""]
    return "\n".join(out)


def render_baseline(comparison: dict, result: dict) -> str:
    """The comparison as a few lines for a job summary."""
    out = ["### Tracked decks against their baseline", ""]
    for name, deck in result["decks"].items():
        out.append(f"- **{name}**: {deck['playable']} of {deck['cards']} cards fully playable ({100 * deck['playable'] / deck['cards']:.0f}%)"
                   if deck["cards"] else f"- **{name}**: no cards")
    for title, key in (("Regressed (played before, no longer does)", "regressed"), ("Now playable (refresh the baseline)", "fixed")):
        if comparison[key]:
            out += ["", f"**{title}:**"] + [f"- {deck}: {', '.join(cards)}" for deck, cards in comparison[key].items()]
    if comparison["new_decks"]:
        out += ["", f"**New decks (not in the baseline yet):** {', '.join(comparison['new_decks'])}"]
    if comparison["missing_decks"]:
        out += ["", f"**In the baseline but not checked:** {', '.join(comparison['missing_decks'])}"]
    return "\n".join(out)


def render_decks(result: dict, top: int = 15) -> str:
    total, playable = result["total"], result["playable"]
    whole = sum(1 for deck in result["decks"].values() if not deck["unplayable"])  # the decks the engine plays in full (#521)
    out = [f"## Coverage for {len(result['decks'])} deck{'s' if len(result['decks']) != 1 else ''}: {playable} of {total} cards fully playable "
           f"({100 * playable / total:.0f}%); {whole} of {len(result['decks'])} play in full" if total else "## Coverage: no cards", ""]
    for name, deck in result["decks"].items():
        out.append(f"- **{name}**: {deck['playable']} of {deck['cards']} cards fully playable ({100 * deck['playable'] / deck['cards']:.0f}%)")
    out += ["", "### What to build, in order (each assuming those above it are built)", "",
            "| # | Piece of work | Cards unlocked | Playable after | Some of the cards | The wording |", "|---|---|---|---|---|---|"]
    shown = [p for p in result["next"] if p["unlocks"]][:top]
    for i, pick in enumerate(shown, 1):
        example = pick["example"].replace("|", "/")[:70]
        family = pick["family"].replace("|", "/")
        out.append(f"| {i} | {family[:60]} | {pick['unlocks']} | {pick['playable_after']:.0%} | {', '.join(pick['cards'][:3])} | {example} |")
    rest = sum(1 for p in result["next"] if p["unlocks"]) - len(shown)
    if rest > 0:
        out.append(f"\n{rest} more pieces of work each unlock at least one card.")
    waiting = [p for p in result["next"] if not p["unlocks"]]
    if waiting and not shown:
        out.append("No single piece of work makes a card playable: every unplayable card needs two or more.")
    if result.get("weighted"):  # the same order with each deck weighed by its metagame share (#565)
        weights = ", ".join(f"{name} {weight:g}" for name, weight in result["weights"].items())
        out += ["", "### The same, weighted by metagame share", "",
                f"Each deck's cards weigh the share its first line names (a deck without one weighs 1): {weights}.", "",
                "| # | Piece of work | Share unlocked | Some of the cards | The wording |", "|---|---|---|---|---|"]
        for i, pick in enumerate([p for p in result["weighted"] if p["unlocks"]][:top], 1):
            example = pick["example"].replace("|", "/")[:70]
            family = pick["family"].replace("|", "/")
            out.append(f"| {i} | {family[:60]} | {pick['unlocks']:g} | {', '.join(pick['cards'][:3])} | {example} |")
    if result["by_kind"]:
        out += ["", "### By kind of text (a card counts under each kind it has)", ""]
        out += [f"- {kind}: {n}" for kind, n in result["by_kind"][:8]]
    out += ["", "### The cards that can't be played yet", ""]
    for name, deck in result["decks"].items():
        if not deck["unplayable"]:
            continue
        out += [f"**{name}** ({len(deck['unplayable'])}):", ""]
        out += [f"- {card}{f' (x{n})' if n > 1 else ''}: {lines[0][:110]}" + (f" (+{len(lines) - 1} more)" if len(lines) > 1 else "")
                for card, n, lines in deck["unplayable"]]
        out.append("")
    return "\n".join(out)


def _popular(names: list[str], rank: dict[str, int]) -> int:
    return sum(1 for n in names if rank.get(n, 10 ** 7) <= POPULAR)


def _best(names: list[str], rank: dict[str, int], count: int = 2) -> str:
    return ", ".join(f"{n} #{rank[n]}" if n in rank else n for n in names[:count])


def render_mechanisms(result: dict, top: int = 25) -> str:
    """The unsupported lines grouped by mechanism, named mechanics and unnamed ones apart, the most useful to build first."""
    rank = result["best_rank"]
    named = {m: g for m, g in result["mechanisms"].items() if m != "Other" and m not in {name for name, _ in MECHANISMS}}
    unnamed = {m: g for m, g in result["mechanisms"].items() if m != "Other" and m not in named}
    out = [f"## Mechanisms: gaps grouped, sorted by the only-gap cards in the top {POPULAR} of EDHREC rank", ""]
    for title, groups in (("Keywords and ability words", named), ("Rules-text mechanisms", unnamed)):
        out += [f"### {title}", "", f"| Mechanism | All cards | Not playable | In top {POPULAR} | Only gap | Only gap, top {POPULAR} | Most played only-gap cards |",
                "|---|---|---|---|---|---|---|"]
        order = sorted(groups.items(), key=lambda kv: (-_popular(kv[1]["only"], rank), -len(kv[1]["only"]), kv[0]))
        for name, g in order[:top]:
            out.append(f"| {name} | {g['all']} | {len(g['cards'])} | {_popular(g['cards'], rank)} | {len(g['only'])} | {_popular(g['only'], rank)} "
                       f"| {_best(g['only'] or g['cards'], rank)} |")
        out.append("")
    if other := result["mechanisms"].get("Other"):
        out += [f"{len(other['cards'])} cards have a line that fits no mechanism.", ""]
    return "\n".join(out)


def render_mechanism(result: dict, name: str, top: int = 25) -> str:
    """The unsupported wordings inside the mechanisms and families whose name contains `name`, the ones on the most popular cards first."""
    rank = result["best_rank"]
    groups = {m: (f"{len(g['cards'])} of {g['all']} cards not playable, {len(g['only'])} with this as the only gap", g["shapes"])
              for m, g in result["mechanisms"].items()}
    groups.update({f: (f"a family, {len(g['cards'])} cards not playable", g["shapes"]) for f, g in result["families"].items()})
    wanted = [m for m in groups if name.lower() in m.lower()]
    if not wanted:
        return f"No mechanism or family matches `{name}`. Try: " + ", ".join(sorted(groups)[:12]) + ", ..."
    out = []
    for mechanism in wanted:
        summary, shapes = groups[mechanism]
        out += [f"### {mechanism}: {summary}", "", f"| Cards | In top {POPULAR} | Unsupported line | Most played |", "|---|---|---|---|"]
        for line, names in sorted(shapes.items(), key=lambda kv: (-_popular(kv[1], rank), -len(kv[1])))[:top]:
            out.append(f"| {len(names)} | {_popular(names, rank)} | `{line.replace('|', '/')}` | {_best(names, rank)} |")
        out.append("")
    return "\n".join(out)


def render_next(result: dict) -> str:
    """The families to build, in order, with what each one unlocks once the ones above it are built."""
    if not result.get("popularity", True):  # no play data: the cards unlocked are all there is to count, and the share is of the pool
        out = [f"## Next targets: the best piece of work first, each assuming those above it are built", "",
               "| # | Family | Cards unlocked | Pool playable after | Also needs | Some of the cards |", "|---|---|---|---|---|---|"]
        for i, pick in enumerate(result["next"], 1):
            out.append(f"| {i} | {pick['family']} | {pick['unlocks']} | {pick['deck_share']:.1%} | {pick['also_needs'] or '-'} | {', '.join(pick['cards'][:3]) or '-'} |")
        out += ["", f"{result['blocked']} unplayable cards have a line no family covers, so they are never counted as unlocked.", ""]
        return "\n".join(out)
    out = [f"## Next targets: the best piece of work first, each assuming those above it are built", "",
           "| # | Family | Cards unlocked | In top " + str(POPULAR) + " | Per deck | Deck playable after | Also needs | Most played |",
           "|---|---|---|---|---|---|---|---|"]
    rank = result["best_rank"]
    for i, pick in enumerate(result["next"], 1):
        out.append(f"| {i} | {pick['family']} | {pick['unlocks']} | {pick['popular']} | {pick['weight']} | {pick['deck_share']:.1%} | {pick['also_needs'] or '-'} "
                   f"| {_best(pick['cards'], rank, 3) or '-'} |")
    out += ["", f"{result['blocked']} unplayable cards have a line no family covers, so they are never counted as unlocked. "
                f"\"Per deck\" is how many cards of a typical deck the row makes playable (the chance a deck holds each card it unlocks, added up; "
                f"see the top of this file for the model), and \"Deck playable after\" the share of the deck playable once it and the rows above are built.", ""]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", default="commander", help="the format whose legal cards are audited (Scryfall's name for it: commander, standard, ...)")
    parser.add_argument("--pool", help="the saved Scryfall cards (default .cache/<format>_pool.json)")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--json", help="also write the numbers here")
    parser.add_argument("--mechanisms", action="store_true", help="also group the gaps by mechanism")
    parser.add_argument("--mechanism", metavar="NAME", help="only the wordings inside the mechanisms or families whose name contains NAME")
    parser.add_argument("--next", action="store_true", help="also rank the families to build next")
    parser.add_argument("--decks", nargs="+", metavar="DECK", help="decklists to check instead of the whole pool: what blocks them and what to build")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json", help="with --decks, the card file")
    parser.add_argument("--baseline", metavar="FILE", help="with --decks, compare with this baseline: exit 1 if a card that played no longer does, or a baseline deck was not checked")
    parser.add_argument("--write-baseline", metavar="FILE", help="with --decks, write the decks' baseline (the names of the cards that can't be played)")
    parser.add_argument("--workers", type=int, default=0, help="processes that read the cards (0: one for each processor, 1: none)")
    args = parser.parse_args(argv)
    if (args.baseline or args.write_baseline) and not args.decks:
        parser.error("--baseline and --write-baseline need --decks")
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.decks:
        from infernal_machine.cards import BulkSource, load_deck

        source = BulkSource(args.bulk)
        decks = {}
        shares: dict[str, float | None] = {}
        for path in args.decks:
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                name = os.path.splitext(os.path.basename(path))[0]
                decks[name] = load_deck(text, source)
                shares[name] = deck_share(text)
            except (OSError, ValueError, LookupError) as error:  # a deck that can't be read must never look like a deck with nothing wrong
                print(f"cannot read the deck {path}: {error}", file=sys.stderr)
                return 2
        # The Standard lists name their archetype's metagame share on their first line (#565); the Commander lists have none and keep
        # the count-based order alone.
        weights = {name: share or 1.0 for name, share in shares.items()} if any(shares.values()) else None
        result = analyze_decks(decks, weights)
        print(render_decks(result, args.top))
        if args.json:
            with open(args.json, "w") as f:
                json.dump(result, f)
        if args.write_baseline:
            with open(args.write_baseline, "w", encoding="utf-8", newline="\n") as f:
                json.dump(baseline_of(result), f, indent=1, sort_keys=True)
                f.write("\n")
        if args.baseline:
            with open(args.baseline, encoding="utf-8") as f:
                comparison = compare_baseline(json.load(f), result)
            print("\n" + render_baseline(comparison, result))
            return 1 if comparison["regressed"] or comparison["missing_decks"] else 0
        return 0
    pool = fetch_pool(args.pool or f".cache/{args.format}_pool.json", format=args.format)
    result = analyze(pool, args.workers, popularity=args.format == "commander")  # EDHREC's rank is Commander's play data
    if args.mechanism:
        print(render_mechanism(result, args.mechanism, args.top))
    else:
        print(render(result, args.top, args.format))
        if args.mechanisms:
            print(render_mechanisms(result, args.top))
        if args.next:
            print(render_next(result))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
