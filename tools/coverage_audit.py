"""How much of the Commander card pool the engine understands, weighted by how much each card is played (the coverage audit,
issue #219).

    python tools/coverage_audit.py [--pool .cache/commander_pool.json] [--top 40] [--json OUT.json]

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

# Pieces of work that are not a keyword: a wording that repeats across cards. A line belongs to every family it matches, so a line
# that mixes two (exile the top card, cast it without paying) needs both.
FAMILIES: tuple[tuple[str, str], ...] = (
    ("Enter as a copy of a permanent (clone)", r"\benters?\b[^.]* as a copy of"),
    ("Token copy of a creature or permanent", r"tokens? (?:that's|that are|which is) (?:a )?cop(?:y|ies) of|create [^.]*\bcop(?:y|ies) of"),
    ("Copy with changes (an except clause)", r"\bcop(?:y|ies) of [^.]*,? except"),
    ("Copy a spell", r"\bcop(?:y|ies) (?:it|that spell|this spell|the spell|each (?:instant|sorcery|spell)|target (?:instant|sorcery|spell)[^.]*spell)\b|\bmay copy (?:it|this|that)\b|\bcopy target (?:instant|sorcery)"),
    ("Copy an ability", r"\bcopy (?:that|target) (?:ability|triggered ability|activated ability)"),
    ("Cast or play from the top of the library", r"(?:cast|play)[^.,]* from the top of (?:your|their|the) library"),
    ("Cast spells from a graveyard", r"(?:you may|may) (?:cast|play)[^.,]* from (?:your|a|an|target|each|their|among|any)[^.]*graveyard|(?:cast|play)[^.,]* from graveyards"),
    ("Exile the top cards, you may play or cast them", r"exile (?:the )?top [^\n]*?(?:you may|may) (?:play|cast)"),
    ("Cast without paying its mana cost", r"without paying (?:its|their) mana cost"),
    ("Can't attack or block unless", r"can't (?:attack|block)(?: or block)? unless"),
    ("Forced combat (must attack, must block, must be blocked)", r"attacks? each (?:combat|turn) if able|blocks? each (?:combat|turn) if able|must be blocked"),
)
_FAMILIES = tuple((name, re.compile(pattern, re.I)) for name, pattern in FAMILIES)
_FAMILY_NAMES = frozenset(name for name, _ in FAMILIES)
_RULE_NAMES = frozenset(name for name, _ in MECHANISMS) | {"Other"}
WEIGHT_KNEE = 1000  # the rank at which a card counts for half of the most played ones
DECK_CARDS = 99  # a Commander deck, apart from its commander
DECK_BASICS = 17  # of which basic lands, assumed (they have no rank and always play)
DECK_TAIL = 2  # how much faster than a card's weight the chance of it being in a deck falls with rank (a guess; see the module docstring)
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
    return _mechanism_of(line, tuple(keywords))


@functools.lru_cache(maxsize=None)  # the same wording is on many cards: 22,000 distinct lines for 170,000 uses (issue #441)
def _mechanism_of(line: str, keywords: tuple[str, ...]) -> str:
    lowered = line.lower()
    for keyword in sorted(keywords, key=len, reverse=True):
        if lowered.startswith(keyword.lower()) and not lowered[len(keyword):len(keyword) + 1].isalpha():  # "Enchant player", not "Enchanted creature ..."
            return keyword
    if word := _ABILITY_WORD.match(line):
        return word[1]
    return next((name for name, pattern in _MECHANISMS if pattern.search(line)), "Other")


def families_of(line: str, keywords: list[str] | tuple[str, ...] = ()) -> frozenset[str]:
    """The pieces of work an unsupported line needs: its keyword or ability word, else every one of `FAMILIES` that matches;
    empty when no family covers it."""
    return _families_of(line, tuple(keywords))


@functools.lru_cache(maxsize=None)
def _families_of(line: str, keywords: tuple[str, ...]) -> frozenset[str]:
    name = _mechanism_of(line, keywords)
    if name not in _RULE_NAMES:
        return frozenset({name})
    return frozenset(family for family, pattern in _FAMILIES if pattern.search(line))


def weight(rank: int | None) -> float:
    """How much a card counts: 1 for the most played, a half at `WEIGHT_KNEE`, nothing for a card with no rank."""
    return 1 / (1 + rank / WEIGHT_KNEE) if rank else 0.0


def _read_cards(pool: list[dict]) -> list[tuple[str | None, list[str]]]:
    """(the error if the report cannot read the card, what it cannot play) for each Scryfall card of the chunk."""
    found: list[tuple[str | None, list[str]]] = []
    for data in pool:
        try:
            found.append((None, unsupported_lines(Card.from_scryfall(data))))
        except Exception as error:  # a card the report cannot even read is a bug to list
            found.append((type(error).__name__, []))
    return found


def read_pool(pool: list[dict], workers: int = 0) -> list[tuple[str | None, list[str]]]:
    """`_read_cards` over the pool, in chunks across processes when it is big enough to be worth them (`workers` 0: one for each
    processor, 1: none). The parse is the slow part of the audit (issue #441)."""
    workers = workers or min(os.cpu_count() or 1, 8)
    if workers == 1 or len(pool) < 2000:
        return _read_cards(pool)
    from concurrent.futures import ProcessPoolExecutor

    size = -(-len(pool) // (workers * 4))
    with ProcessPoolExecutor(workers) as executor:
        return [item for chunk in executor.map(_read_cards, [pool[i:i + size] for i in range(0, len(pool), size)]) for item in chunk]


def inclusion_scale(ranks: list[int]) -> float:
    """The scale that makes the inclusion probabilities of these cards add up to the deck's nonbasic slots (all of them 1 if the
    cards are too few to fill the deck)."""
    slots = DECK_CARDS - DECK_BASICS
    if sum(1 for _ in ranks) <= slots:
        return float("inf")
    low, high = 0.0, 1e7
    weights = [weight(r) ** DECK_TAIL for r in ranks]  # (once, not at every one of the 80 steps)
    for _ in range(80):
        mid = (low + high) / 2
        if sum(min(1.0, mid * w) for w in weights) < slots:
            low = mid
        else:
            high = mid
    return high


def inclusion(rank: int | None, scale: float) -> float:
    """The chance that a typical deck holds a card of this rank (0 without one)."""
    return min(1.0, scale * weight(rank) ** DECK_TAIL) if rank else 0.0


def deck_coverage(entries: list[tuple[int | None, bool]], scale: float) -> dict:
    """The typical deck's numbers from (rank, fully playable) for every card: the expected cards it can play, the expected cards it
    can't, the share of the deck that is playable and the chance that all of it is."""
    playable = sum(inclusion(r, scale) for r, ok in entries if ok)
    broken = [inclusion(r, scale) for r, ok in entries if not ok]
    clean = 0.0 if any(p >= 1 for p in broken) else math.exp(sum(math.log1p(-p) for p in broken))
    return {"cards": DECK_CARDS, "basics": DECK_BASICS, "playable": DECK_BASICS + playable, "unplayable": sum(broken),
            "share": (DECK_BASICS + playable) / DECK_CARDS, "clean": clean, "scale": scale if scale != float("inf") else None}


def next_targets(cards: list[tuple[str, int | None, frozenset[str]]], limit: int = 15, weigh=weight) -> list[dict]:
    """The families to build, best first. `cards` are (name, rank, families the card still needs). Greedy: take the family whose
    cards weigh the most (a card needing several shares its weight between those not yet built), assume it built, repeat. `weigh`
    maps a rank to a card's weight: `weight`, or an inclusion probability to count cards per deck."""
    need = {name: families for name, _, families in cards}
    rank = {name: r for name, r, _ in cards}
    by_family: dict[str, list[str]] = collections.defaultdict(list)
    for name, families in need.items():
        for family in families:
            by_family[family].append(name)
    built: set[str] = set()
    picks: list[dict] = []
    while len(picks) < limit:
        scores = {f: sum(weigh(rank[n]) / len(need[n] - built) for n in names)
                  for f, names in by_family.items() if f not in built}
        if not scores or max(scores.values()) <= 0:
            break
        best = min(scores, key=lambda f: (-scores[f], -len(by_family[f]), f))
        built.add(best)
        unlocked = sorted((n for n in by_family[best] if need[n] <= built), key=lambda n: rank[n] or 10 ** 7)
        waiting = collections.Counter(f for n in by_family[best] for f in need[n] - built)
        picks.append({"family": best, "unlocks": len(unlocked), "popular": sum(1 for n in unlocked if rank[n] and rank[n] <= POPULAR),
                      "weight": round(sum(weigh(rank[n]) for n in unlocked), 3), "also_needs": waiting.most_common(1)[0][0] if waiting else "",
                      "cards": unlocked[:3]})
    return picks


_REMINDER = re.compile(r"\([^)]*\)")


def card_mechanisms(card: Card, keywords: list[str] | tuple[str, ...] = ()) -> set[str]:
    """The mechanisms any line of the card's text belongs to (reminder text left out), playable or not."""
    lines = (_REMINDER.sub("", line).strip() for line in card.oracle_text.split("\n"))
    return {mechanism_of(line, keywords) for line in lines if line}


def kind_of(card: Card) -> str:
    return next((word for word in TYPES if word in card.type_line), "Other")


def analyze(pool: list[dict], workers: int = 0) -> dict:
    """The audit's numbers for a list of Scryfall card objects."""
    total = playable = 0
    by_type: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
    ranked: list[tuple[int, bool]] = []
    entries: list[tuple[int | None, bool]] = []  # (rank, fully playable) of every card
    shapes: dict[str, set[str]] = collections.defaultdict(set)
    only_gap: dict[str, set[str]] = collections.defaultdict(set)
    one_gap = 0
    crashes: list[str] = []
    best_rank: dict[str, int] = {}
    everywhere: collections.Counter[str] = collections.Counter()  # cards per mechanism, playable or not
    needs: list[tuple[str, int | None, frozenset[str]]] = []  # each unplayable card and the families it needs
    blocked = 0  # unplayable cards with a line no family covers
    family_shapes: dict[str, dict[str, set[str]]] = collections.defaultdict(lambda: collections.defaultdict(set))
    groups: dict[str, dict[str, Any]] = collections.defaultdict(lambda: {"cards": set(), "only": set(), "shapes": collections.defaultdict(set)})
    for data, (error, lines) in zip(pool, read_pool(pool, workers)):
        if error:
            crashes.append(f"{data.get('name')}: {error}")
            continue
        card = Card.from_scryfall(data)
        total += 1
        kind = kind_of(card)
        by_type[kind][0] += 1
        if not lines:
            playable += 1
            by_type[kind][1] += 1
        entries.append((data.get("edhrec_rank"), not lines))
        if data.get("edhrec_rank"):
            ranked.append((data["edhrec_rank"], not lines))
            best_rank[card.name] = data["edhrec_rank"]
        if len(lines) == 1:
            one_gap += 1
            only_gap[shape(lines[0])].add(card.name)
        for line in lines:
            shapes[shape(line)].add(card.name)
        mechanisms = [mechanism_of(line, data.get("keywords") or ()) for line in lines]
        if lines:
            per_line = [families_of(line, data.get("keywords") or ()) for line in lines]
            if not all(per_line):
                blocked += 1
            else:
                needs.append((card.name, data.get("edhrec_rank"), frozenset().union(*per_line)))
            for line, families in zip(lines, per_line):
                for family in families & _FAMILY_NAMES:
                    family_shapes[family][shape(line)].add(card.name)
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
    scale = inclusion_scale([r for r, _ in ranked])
    deck = deck_coverage(entries, scale)
    picks = next_targets(needs, weigh=lambda rank: inclusion(rank, scale))
    gained = 0.0
    for pick in picks:  # what the deck's playable share is once this piece and those above it are built
        gained += pick["weight"]
        pick["deck_share"] = (deck["playable"] + gained) / DECK_CARDS
    return {"total": total, "playable": playable, "by_type": dict(by_type), "popular": popular, "one_gap": one_gap,
            "shapes": {s: by_rank(names) for s, names in shapes.items()},
            "only_gap": {s: by_rank(names) for s, names in only_gap.items()},
            "best_rank": best_rank, "crashes": crashes, "blocked": blocked, "next": picks, "deck": deck,
            "families": {f: {"cards": by_rank({n for names in shapes_.values() for n in names}),
                             "shapes": {s: by_rank(names) for s, names in shapes_.items()}} for f, shapes_ in family_shapes.items()},
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
    deck = result["deck"]
    out += ["", f"A typical {deck['cards'] + 1}-card deck ({deck['basics']} basic lands, the rest chosen by how played each card is) is "
                f"{deck['share']:.1%} fully playable: about {deck['unplayable']:.1f} of its cards the engine cannot play, and a "
                f"{deck['clean']:.1%} chance that every one of them is playable."]
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


def analyze_decks(decks: dict[str, Any]) -> dict:
    """What stops the given decks (name -> `Deck`) from being fully playable, and the order of work that unlocks the most cards.
    Every copy of a card counts (a piece of work that unlocks a card with two copies unlocks two cards); a line no family covers is a
    piece of work of its own, named by its wording."""
    per_deck: dict[str, dict] = {}
    needs: list[tuple[str, int | None, frozenset[str]]] = []
    example: dict[str, str] = {}
    total = playable = 0
    for deck_name, deck in decks.items():
        cards = deck.commanders + deck.main
        copies = collections.Counter(c.name for c in cards)
        by_name = {c.name: c for c in cards}
        unplayable: list[tuple[str, int, list[str]]] = []
        for name in copies:
            lines = unsupported_lines(by_name[name])
            if not lines:
                continue
            unplayable.append((name, copies[name], lines))
            items: set[str] = set()
            for line in lines:
                found = families_of(line) or frozenset({"Other: " + shape(line)})
                items |= found
                for item in found:
                    example.setdefault(item, line)
            needs.append((f"{deck_name}\x00{name}", copies[name], frozenset(items)))
        broken = sum(n for _, n, _ in unplayable)
        per_deck[deck_name] = {"cards": len(cards), "playable": len(cards) - broken, "unplayable": unplayable}
        total += len(cards)
        playable += len(cards) - broken
    picks = next_targets(needs, limit=max(len(needs), 1) * 4, weigh=float)
    gained = 0.0
    for pick in picks:
        gained += pick["weight"]
        pick["unlocks"] = round(pick["weight"])  # cards, counting every copy
        pick["cards"] = [key.split("\x00", 1)[1] for key in pick["cards"]]
        pick["playable_after"] = (playable + gained) / total if total else 0.0
        pick["example"] = example.get(pick["family"], "")
    by_kind: collections.Counter[str] = collections.Counter()
    for deck in per_deck.values():
        for _, n, lines in deck["unplayable"]:
            for kind in {mechanism_of(line) for line in lines}:
                by_kind[kind] += n
    return {"decks": per_deck, "next": picks, "total": total, "playable": playable, "by_kind": by_kind.most_common()}


def baseline_of(result: dict) -> dict:
    """What `--write-baseline` keeps of an `analyze_decks` result: for each deck, its size and the names of the cards the engine can't play.
    Names, not counts, so a card that stops working is named even when another one starts working the same week."""
    return {"decks": {name: {"cards": deck["cards"], "unplayable": sorted(card for card, _, _ in deck["unplayable"])}
                      for name, deck in sorted(result["decks"].items())}}


def compare_baseline(baseline: dict, result: dict) -> dict:
    """The tracked decks against their baseline (#475). `regressed`: cards that played in the baseline and no longer do, the one thing
    that fails the weekly job (a parser change, or a card whose Oracle text changed); `fixed`: cards that now play, a reminder to
    refresh the baseline; `new_decks`: decks the baseline has not seen, recorded and not failed; `missing_decks`: decks the baseline
    has that were not checked, which fails (a deck file that went missing must not read as 'nothing got worse')."""
    kept = baseline.get("decks", {})
    now = {name: {card for card, _, _ in deck["unplayable"]} for name, deck in result["decks"].items()}
    regressed: dict[str, list[str]] = {}
    fixed: dict[str, list[str]] = {}
    for name, unplayable in now.items():
        if name not in kept:
            continue
        before = set(kept[name]["unplayable"])
        if unplayable - before:
            regressed[name] = sorted(unplayable - before)
        if before - unplayable:
            fixed[name] = sorted(before - unplayable)
    return {"regressed": regressed, "fixed": fixed, "new_decks": sorted(set(now) - set(kept)), "missing_decks": sorted(set(kept) - set(now))}


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
    out = [f"## Coverage for {len(result['decks'])} deck{'s' if len(result['decks']) != 1 else ''}: {playable} of {total} cards fully playable "
           f"({100 * playable / total:.0f}%)" if total else "## Coverage: no cards", ""]
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
    parser.add_argument("--pool", default=".cache/commander_pool.json")
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
        for path in args.decks:
            try:
                with open(path, encoding="utf-8") as f:
                    decks[os.path.splitext(os.path.basename(path))[0]] = load_deck(f.read(), source)
            except (OSError, ValueError, KeyError) as error:  # a deck that can't be read must never look like a deck with nothing wrong
                print(f"cannot read the deck {path}: {error}", file=sys.stderr)
                return 2
        result = analyze_decks(decks)
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
    result = analyze(fetch_pool(args.pool), args.workers)
    if args.mechanism:
        print(render_mechanism(result, args.mechanism, args.top))
    else:
        print(render(result, args.top))
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
