"""How much of the Commander card pool the engine understands, weighted by how much each card is played (the coverage audit,
issue #219).

    python tools/coverage_audit.py [--pool .cache/commander_pool.json] [--top 40] [--json OUT.json]

Fetches every Commander-legal paper card from Scryfall's search API (about 185 pages, a few minutes; the result is kept in
`--pool` and reused for a week), runs the report's `unsupported_lines` over each card, and prints a markdown summary: the share
of fully playable cards overall, by card type and by EDHREC rank (Scryfall carries it), the unsupported lines that appear on the
most cards, and those that are a card's only gap (the cheapest wins). "Fully playable" means the engine understands every line,
not that the card behaves correctly.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import Card  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402

SEARCH = "legal:commander game:paper -t:token -is:funny"
TYPES = ("Creature", "Planeswalker", "Land", "Instant", "Sorcery", "Artifact", "Enchantment", "Battle")
RANK_BUCKETS = (100, 500, 1000, 2500, 5000, 10000)


def fetch_pool(path: str, max_age_days: float = 7.0, pause: float = 0.11) -> list[dict]:
    """The Commander-legal paper cards as Scryfall's JSON, from `path` if it is fresh, else from the search API."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        with open(path) as f:
            return json.load(f)
    url = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": SEARCH, "unique": "cards"})
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


def shape(line: str) -> str:
    """An unsupported line with its mana symbols and numbers blurred, so the same wording on different cards groups together."""
    line = re.sub(r"\{[^}]*\}", "{M}", line)
    line = re.sub(r"\b\d+\b", "N", line)
    line = re.sub(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b", "N", line)
    return line[:100]


def kind_of(card: Card) -> str:
    return next((word for word in TYPES if word in card.type_line), "Other")


def analyze(pool: list[dict]) -> dict:
    """The audit's numbers for a list of Scryfall card objects."""
    total = playable = 0
    by_type: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    ranked: list[tuple[int, bool]] = []
    shapes: dict[str, set[str]] = collections.defaultdict(set)
    only_gap: dict[str, set[str]] = collections.defaultdict(set)
    one_gap = 0
    crashes: list[str] = []
    best_rank: dict[str, int] = {}
    for data in pool:
        try:
            card = Card.from_scryfall(data)
            lines = unsupported_lines(card)
        except Exception as error:  # a card the report cannot even read is a bug to list
            crashes.append(f"{data.get('name')}: {type(error).__name__}")
            continue
        total += 1
        kind = kind_of(card)
        by_type[kind][0] += 1
        if not lines:
            playable += 1
            by_type[kind][1] += 1
        if data.get("edhrec_rank"):
            ranked.append((data["edhrec_rank"], not lines))
            best_rank[card.name] = data["edhrec_rank"]
        if len(lines) == 1:
            one_gap += 1
            only_gap[shape(lines[0])].add(card.name)
        for line in lines:
            shapes[shape(line)].add(card.name)
    ranked.sort()
    popular = {n: (sum(ok for _, ok in ranked[:n]), min(n, len(ranked))) for n in RANK_BUCKETS}
    return {"total": total, "playable": playable, "by_type": dict(by_type), "popular": popular, "one_gap": one_gap,
            "shapes": {s: sorted(names, key=lambda n: best_rank.get(n, 10 ** 7)) for s, names in shapes.items()},
            "only_gap": {s: sorted(names, key=lambda n: best_rank.get(n, 10 ** 7)) for s, names in only_gap.items()},
            "best_rank": best_rank, "crashes": crashes}


def render(result: dict, top: int = 40) -> str:
    total, playable = result["total"], result["playable"]
    out = [f"## Coverage audit: {playable} of {total} Commander-legal cards fully playable ({100 * playable / total:.1f}%)", ""]
    out.append("| Card type | Fully playable |\n|---|---|")
    for kind, (count, ok) in sorted(result["by_type"].items(), key=lambda kv: -kv[1][0]):
        out.append(f"| {kind} | {ok} of {count} ({100 * ok / count:.0f}%) |")
    out += ["", "| Most played (EDHREC rank) | Fully playable |\n|---|---|"]
    for n, (ok, of) in result["popular"].items():
        out.append(f"| top {n} | {ok} of {of} ({100 * ok / of:.0f}%) |" if of else f"| top {n} | no ranked cards |")
    gaps = len(result["shapes"])
    singles = sum(1 for names in result["shapes"].values() if len(names) == 1)
    out += ["", f"{result['one_gap']} cards have exactly one unsupported line. There are {gaps} distinct unsupported lines, "
                f"{singles} of them on a single card.", ""]
    rank = result["best_rank"]

    def table(title: str, groups: dict[str, list[str]]) -> None:
        out.append(f"### {title}\n\n| Cards | Unsupported line | Most played |\n|---|---|---|")
        for line, names in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:top]:
            best = ", ".join(f"{n} #{rank[n]}" if n in rank else n for n in names[:2])
            out.append(f"| {len(names)} | `{line.replace('|', '/')}` | {best} |")
        out.append("")

    table("Unsupported lines on the most cards", result["shapes"])
    table("Lines that are a card's only gap", result["only_gap"])
    if result["crashes"]:
        out += ["### Cards the report could not read", ""] + [f"- {c}" for c in result["crashes"][:20]] + [""]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--json", help="also write the numbers here")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    result = analyze(fetch_pool(args.pool))
    print(render(result, args.top))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
