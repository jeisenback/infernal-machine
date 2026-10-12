"""How much of the Commander card pool the engine understands, weighted by how much each card is played (the coverage audit,
issue #219).

    python tools/coverage_audit.py [--pool .cache/commander_pool.json] [--top 40] [--json OUT.json]

Fetches every Commander-legal paper card from Scryfall's search API (about 185 pages, a few minutes; the result is kept in
`--pool` and reused for a week), runs the report's `unsupported_lines` over each card, and prints a markdown summary: the share
of fully playable cards overall, by card type and by EDHREC rank (Scryfall carries it), the unsupported lines that appear on the
most cards, and those that are a card's only gap (the cheapest wins). "Fully playable" means the engine understands every line,
not that the card behaves correctly.

    python tools/coverage_audit.py --mechanisms          # also group the gaps by mechanism, ranked by popularity
    python tools/coverage_audit.py --mechanism "Copy"    # the wordings inside one mechanism (a substring of its name)

A mechanism is a keyword or ability word at the start of an unsupported line, or else the first of the `MECHANISMS` patterns that
matches it; the patterns are a heuristic, so the groups are a guide to what to build next, not exact counts. "All cards" counts every card with a line in the mechanism, playable or not, so a row shows how much of it is covered. A card's "only gap"
mechanism is the one that holds all its unsupported lines, so building it alone could make the card playable. The tables are sorted
by the only-gap cards in the top `POPULAR` of EDHREC rank.
"""

from __future__ import annotations

import argparse
import collections
import json
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

SEARCH = "legal:commander game:paper -t:token -is:funny"
TYPES = ("Creature", "Planeswalker", "Land", "Instant", "Sorcery", "Artifact", "Enchantment", "Battle")
RANK_BUCKETS = (100, 500, 1000, 2500, 5000, 10000)
POPULAR = 5000  # a card at this EDHREC rank or better counts as popular

# Unnamed mechanisms, most specific first: the first pattern that matches an unsupported line names its mechanism.
MECHANISMS: tuple[tuple[str, str], ...] = (
    ("Attack/block restrictions", r"can't (?:attack|block)(?: or block)? (?:unless|if|except)|can't be blocked (?:except|by)|can block only|must be blocked|blocks? each combat if able|attacks? each (?:combat|turn) if able|can't attack or block|can't attack you|can attack as though"),
    ("Planeswalker loyalty abilities", r"^[+\u2212\-\u2013]?(?:\d+|X|0)\s?:|^\[[+\u2212\-\u2013]\d+\]:"),
    ("Saga, Class, Level, Room, Case", r"\bsaga\b|\bclass\b|\blevel \d|\broom\b|\bcase\b|\bsolved\b|\bchapter\b|\bunlock"),
    ("Face-down: morph, manifest, disguise, cloak", r"face[- ](?:down|up)|\bmanifest|\bcloak|\bmorph|\bdisguise"),
    ("Copy effects", r"\bcop(?:y|ies)\b|becomes a copy"),
    ("Gain control", r"gain control|control of target|exchange control|you control enchanted"),
    ("Fight and bite", r"\bfights?\b|deals damage equal to its power to"),
    ("Play or cast from exile and other zones", r"exile .* you may (?:play|cast)|you may play .* from exile|may cast .* from (?:exile|your graveyard|the top of your library|among|a graveyard|your library)|cast .* from exile|play lands from|you may play (?:lands|cards)|may cast (?:spells|it|that card)|without paying (?:its|their) mana cost"),
    ("Library: search, look, scry", r"search your library|search target|look at the top|reveal the top|reveal cards from the top|top card of (?:your|that|each)|top \w+ cards|from among them|\bscry|\bsurveil|library"),
    ("Graveyard recursion and graveyard matters", r"graveyard|from exile to|return .* to the battlefield|\bdredge"),
    ("Mill", r"\bmills?\b|into your graveyard"),
    ("Discard and hand", r"discard|your hand|their hand|hand size|cards in hand|random card"),
    ("Counters on permanents", r"\bproliferate|\bcounters? on|remove .* counter|put .* counter|loyalty counter|\bcounters? from|with .* counter"),
    ("Counter a spell or ability, triggered abilities", r"counter (?:target|all|that|it)\b|can't be countered|unless (?:its controller|that player|they) pays?|spell or ability|activated or triggered|triggers? an additional|triggered ability|activated abilit"),
    ("Dynamic power/toughness", r"power is equal|toughness is equal|power and toughness are each equal|equal to the number of|equal to the total|for each .* you control gets|where X is"),
    ("Timing and casting restrictions", r"cast this spell only|activate only|only during|only as a sorcery|as though (?:it|.*) had flash|any time you could cast"),
    ("Cost reduction and alternative costs", r"costs? \{?\d?\}? ?less|cost .* less|rather than pay|costs? \{[^}]+\} more|additional cost|alternative cost|as an additional|cast this spell for|spend only|spend mana"),
    ("Regenerate, hexproof, protection", r"regenerat|can't be the target|hexproof|shroud|\bward\b|protection from"),
    ("Global restrictions (players can't ...)", r"players can't|can't (?:search|cast|gain life|draw|activate|be sacrificed|lose)|don't untap|doesn't untap|\bskips?\b"),
    ("Sweepers: damage or destroy each/all", r"damage to each|each non|each other creature|destroy all|all creatures|each creature"),
    ("Combat damage triggers and rules", r"deals? combat damage|excess damage|assign(?:s|ed)? (?:its |their )?combat damage|all combat damage|combat damage can|combat damage that"),
    ("Damage prevention and redirection", r"prevent (?:all|the next|that)|damage .* is dealt to|redirect"),
    ("Vehicles, crew, saddle", r"vehicle|\bcrew\b|saddle|\bmount"),
    ("Token creation", r"create(?:s)? .*token|tokens? you control|token creature|treasure|food token|clue|blood token|map token|powerstone|incubator|role token|junk token"),
    ("Mana production", r"add (?:\{|one|two|three|X|an amount)|mana of any|mana abilities|doesn't empty|unspent mana|\badds? \{"),
    ("Sacrifice", r"sacrific"),
    ("Life total", r"gain \w+ life|lose \w+ life|loses? life|gains? life|life total|pay \d+ life|lifelink|life equal|starting life|paying life|life more|life less|your life"),
    ("Draw cards", r"\bdraws?\b"),
    ("Destroy, exile, bounce, tap", r"destroy|exile target|exile all|exile each|return target .* to (?:its|their) owner's hand|return all|tap target|untap target|tap all|untap all|phase out|goad|tapped"),
    ("Stat changes and granted abilities", r"gets? [+\-]\d|base power|power and toughness|has base|gains? (?:flying|haste|trample|vigilance|deathtouch|menace|lifelink|indestructible|hexproof|first strike|reach|ward|protection)|have (?:flying|haste|trample)|loses all|becomes? (?:a|an|the) |is a \d/\d|in addition to its other"),
    ("Auras and Equipment", r"attach|enchanted|equipped|enchant |equip "),
    ("Extra turns, phases and turn structure", r"extra turn|additional combat|extra combat|additional main|beginning of (?:the next|each|your) (?:end|upkeep|draw|combat|main)|during your (?:turn|upkeep)|each upkeep|at end of combat|untap step|time counter"),
    ("Replacement effects (would, instead)", r"\binstead\b|would (?:be |enter|die|draw|gain|deal|put|create)|enters? (?:the battlefield )?(?:tapped|with|as)|as .* enters"),
    ("Voting, dice, coins, choices", r"\bvote|\bvoting|\broll|flip a coin|\bcoin\b|choose (?:a|an|one|two|three|target|any|up|each)|\bchosen\b|name a|opponent chooses|of your choice|secretly"),
    ("Monarch, initiative, dungeons, energy, experience, poison, the Ring", r"monarch|initiative|dungeon|venture|energy|\{e\}|experience|poison|toxic|infect|commander|ring-bearer|the ring|\bday\b|\bnight\b|\bspeed\b|radiation"),
    ("Triggers: enters, dies, leaves, attacks", r"^(?:when|whenever|at)\b.*(?:enter|dies|die|leave|attack|cast|becomes|put into)|enters|dies|leaves the battlefield"),
    ("Win, lose and game state", r"win the game|lose the game|loses the game|wins the game|draw the game|game ends|restart|emblem|planechase|\bplane\b|scheme|sticker|attraction|contraption"),
    ("Spells matter: cast triggers, storm, spell types", r"instant or sorcery|noncreature spell|creature spell|spells? you cast|cast (?:a|an|your|a second|a third|two)|\bstorm\b|cascade|magecraft|multicolored|spell(?:s)? (?:from|with)"),
    ("Creature types: changeling, party", r"changeling|all creature types|creature type|is every creature|\bparty\b|\bdevoid\b"),
    ("Lands and landfall", r"\blands?\b|landfall|basic land|plains|island|swamp|mountain|forest|battlefield tapped"),
    ("Modal, reflexive and conditional structure", r"\u2022|choose one|choose two|\bwhen you do\b|you may pay|if you do|if you don't|if able|may have|may choose|unless you|then if|if that"),
)
_MECHANISMS = tuple((name, re.compile(pattern, re.I)) for name, pattern in MECHANISMS)
_ABILITY_WORD = re.compile(r"^([A-Z][A-Za-z' !-]{2,24}) \u2014 ")


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


def mechanism_of(line: str, keywords: list[str] | tuple[str, ...] = ()) -> str:
    """The mechanism an unsupported line belongs to: the card's own keyword it starts with, an ability word ("Delirium \u2014 ..."),
    or the first of `MECHANISMS` that matches; "Other" when nothing does."""
    lowered = line.lower()
    for keyword in sorted(keywords, key=len, reverse=True):
        if lowered.startswith(keyword.lower()) and not lowered[len(keyword):len(keyword) + 1].isalpha():  # "Enchant player", not "Enchanted creature ..."
            return keyword
    if word := _ABILITY_WORD.match(line):
        return word[1]
    return next((name for name, pattern in _MECHANISMS if pattern.search(line)), "Other")


_REMINDER = re.compile(r"\([^)]*\)")


def card_mechanisms(card: Card, keywords: list[str] | tuple[str, ...] = ()) -> set[str]:
    """The mechanisms any line of the card's text belongs to (reminder text left out), playable or not."""
    lines = (_REMINDER.sub("", line).strip() for line in card.oracle_text.split("\n"))
    return {mechanism_of(line, keywords) for line in lines if line}


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
    everywhere: collections.Counter[str] = collections.Counter()  # cards per mechanism, playable or not
    groups: dict[str, dict[str, Any]] = collections.defaultdict(lambda: {"cards": set(), "only": set(), "shapes": collections.defaultdict(set)})
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
        mechanisms = [mechanism_of(line, data.get("keywords") or ()) for line in lines]
        everywhere.update(card_mechanisms(card, data.get("keywords") or ()) | set(mechanisms))
        for line, mechanism in zip(lines, mechanisms):
            groups[mechanism]["cards"].add(card.name)
            groups[mechanism]["shapes"][shape(line)].add(card.name)
            if set(mechanisms) == {mechanism}:
                groups[mechanism]["only"].add(card.name)
    ranked.sort()

    def by_rank(names: set[str]) -> list[str]:
        return sorted(names, key=lambda n: best_rank.get(n, 10 ** 7))
    popular = {n: (sum(ok for _, ok in ranked[:n]), min(n, len(ranked))) for n in RANK_BUCKETS}
    return {"total": total, "playable": playable, "by_type": dict(by_type), "popular": popular, "one_gap": one_gap,
            "shapes": {s: by_rank(names) for s, names in shapes.items()},
            "only_gap": {s: by_rank(names) for s, names in only_gap.items()},
            "best_rank": best_rank, "crashes": crashes,
            "mechanisms": {m: {"all": everywhere[m], "cards": by_rank(g["cards"]), "only": by_rank(g["only"]),
                               "shapes": {s: by_rank(names) for s, names in g["shapes"].items()}} for m, g in groups.items()}}


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
    """The unsupported wordings inside the mechanisms whose name contains `name`, the ones on the most popular cards first."""
    rank = result["best_rank"]
    wanted = [m for m in result["mechanisms"] if name.lower() in m.lower()]
    if not wanted:
        return f"No mechanism matches `{name}`. Try: " + ", ".join(sorted(result["mechanisms"])[:12]) + ", ..."
    out = []
    for mechanism in wanted:
        g = result["mechanisms"][mechanism]
        out += [f"### {mechanism}: {len(g['cards'])} of {g['all']} cards not playable, {len(g['only'])} with this as the only gap", "",
                f"| Cards | In top {POPULAR} | Unsupported line | Most played |", "|---|---|---|---|"]
        for line, names in sorted(g["shapes"].items(), key=lambda kv: (-_popular(kv[1], rank), -len(kv[1])))[:top]:
            out.append(f"| {len(names)} | {_popular(names, rank)} | `{line.replace('|', '/')}` | {_best(names, rank)} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--json", help="also write the numbers here")
    parser.add_argument("--mechanisms", action="store_true", help="also group the gaps by mechanism")
    parser.add_argument("--mechanism", metavar="NAME", help="only the wordings inside the mechanisms whose name contains NAME")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    result = analyze(fetch_pool(args.pool))
    if args.mechanism:
        print(render_mechanism(result, args.mechanism, args.top))
    else:
        print(render(result, args.top))
        if args.mechanisms:
            print(render_mechanisms(result, args.top))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
