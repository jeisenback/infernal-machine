"""Tuning report: which cards earn their slot, and what a different land count or a candidate card would do.

    python -m infernal_machine.tune DECKLIST [--games N] [--turns N] [--seed N] [--try "Card Name"]... [--suggest-combos [N]]

It scores a deck by what `simulate` sees: the mana a game spends on spells plus the damage it deals by the last turn
(`game_value`). To measure a card it replays the same games with that card replaced by a blank, so every shuffle is
the same and the difference is the card's contribution; only the games where the card was drawn can differ, so only
those are replayed. This rewards deploying mana and creatures. It cannot see what a card's text does (removal, card
draw, counterspells, life gain), so a low score means "does little in a goldfish", not "bad card": read it next to the
card's job in the deck.

`--suggest-combos` also tries the cards Commander Spellbook says are one card from completing a combo the deck is close to (the N that
complete the most, ten by default), and says which combos each would complete and what they produce.
"""

from __future__ import annotations

import io
import math
import sys
from collections import Counter
from dataclasses import dataclass, field, replace

from .analysis import is_land
from .brackets import BracketReport, analyze, bracket_floor, is_mass_land_denial
from .cards import Card, Deck
from .combos import Combo, SpellbookSource
from .commander import copy_limit
from .formats import COMMANDER, FORMATS, NO_HOUSE_RULES, STANDARD, HouseRules, add_house_rules_arguments, format_of, house_rules
from .manabase import ManaBase, analyze_mana_base, format_mana_base
from .report import unplayable_cards, unplayable_note, unsupported_lines
from .simulate import game_value, play_game, play_games

BLANK = Card(name="(blank)", type_line="Sorcery")  # no cost, so it is never cast: a dead card in the same slot
DEAD_WEIGHT = 0.5  # cast less often than this when drawn, and it is flagged


@dataclass
class Effect:
    """A change's average effect on a game's value, over all games, with its standard error."""
    delta: float
    error: float

    @property
    def clear(self) -> bool:
        return abs(self.delta) > 2 * self.error


@dataclass
class CardImpact:
    name: str
    copies: int
    value: Effect  # what the card adds per game (with it minus without it)
    seen_rate: float
    cast_when_seen: float
    note: str = ""


@dataclass
class TuningReport:
    games: int
    turns: int
    baseline: float  # average game value
    cards: list[CardImpact]  # weakest first
    lands: dict[int, Effect]  # change in land count -> effect on value
    swaps: list[tuple[str, str, Effect]] = field(default_factory=list)  # (card tried, card it replaces, effect), best first
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (candidate, why it was not tried)
    unplayable: list[tuple[str, int, str]] = field(default_factory=list)  # (card, copies, first line) the engine can't fully play
    candidate_unplayable: dict[str, str] = field(default_factory=dict)  # candidate -> the first line of its text the engine can't read
    bracket: BracketReport | None = None  # what the deck's cards say about its Commander Bracket (None for a deck with no commander)
    swap_notes: dict[str, str] = field(default_factory=dict)  # candidate -> what trying it would do to the Bracket, when it does something
    mana_base: ManaBase | None = None  # sources of each color the deck needs and has (None for a deck with no colored symbols)
    suggestions: list["ComboSuggestion"] = field(default_factory=list)  # the cards one away from completing combos (`--suggest-combos`)


@dataclass
class ComboSuggestion:
    """A card Commander Spellbook says would complete combos the deck is one card from."""
    card: str
    combos: list[Combo]  # the combos it would complete, the most played first; each lists the deck's cards and this one


def combo_suggestions(deck: Deck, almost: list[Combo], limit: int = 10) -> list[ComboSuggestion]:
    """The cards that would complete the most of the combos `almost` (Spellbook's combos one card away) holds, then the one with the
    most played combo, then by name; at most `limit`. A combo missing more than one card of the deck's (or none) is left out."""
    held = {card.name for card in deck.commanders + deck.main}
    by_card: dict[str, list[Combo]] = {}
    for combo in almost:
        missing = [name for name in combo.cards if name not in held]
        if len(missing) == 1:
            by_card.setdefault(missing[0], []).append(combo)
    ranked = sorted(by_card.items(), key=lambda item: (-len(item[1]), -max(c.popularity for c in item[1]), item[0]))
    return [ComboSuggestion(name, sorted(combos, key=lambda c: (-c.popularity, c.label()))) for name, combos in ranked[:limit]]


def candidate_problem(deck: Deck, card: Card, house: HouseRules = NO_HOUSE_RULES) -> str | None:
    """Why `card` can't be swapped into `deck`, or None. A Commander deck (one with a commander) needs the card inside the
    commander's color identity, legal in Commander, and not past its copy limit (singleton, so a card already in it is out).
    A deck with no commander is a constructed deck (Standard unless it names another format): the card must be legal in its format
    and under four copies in main and sideboard (one for a card on Vintage's restricted list). A card `house` lets in (#528) may be
    illegal in the format; the other rules still hold for it."""
    in_deck = sum(1 for c in deck.main + deck.commanders + deck.sideboard if c.name == card.name)
    if not deck.commanders:  # a constructed deck: legal in its format, and the sideboard counts toward the four copies
        fmt = FORMATS.get(deck.format, STANDARD)
        if not card.legal_in(fmt.legality) and not house.permits(card, fmt):
            return f"not legal in {fmt.label}"
        limit = 1 if fmt.legality in card.restricted else copy_limit(card, fmt.copy_limit)
        return None if limit is None or in_deck < limit else f"already at {limit} copies"
    identity = {color for c in deck.commanders for color in c.color_identity}
    if set(card.color_identity) - identity:
        return f"outside the commander's color identity ({''.join(sorted(set(card.color_identity) - identity))})"
    fmt = FORMATS.get(deck.format, COMMANDER)  # Commander, or the commander format the deck names (Brawl, Pauper Commander, ...)
    if not card.legal_in(fmt.legality) and not house.permits(card, fmt):
        return f"not legal in {fmt.label}"
    limit = copy_limit(card)
    if limit is not None and in_deck >= limit:
        return "already in the deck" if limit == 1 else f"already at the limit of {limit}"
    return None


def _bracket_notes(deck: Deck, swaps: list, tried: list[Card]) -> dict[str, str]:
    """For each swap that changes the deck's Game Changers or brings in mass land denial: what that does to the Bracket."""
    current = analyze(deck)
    notes = {}
    in_deck = {c.name: c for c in deck.main}  # the card a swap replaces is looked up by name
    by_name = {c.name: c for c in tried}
    for new, old, _ in swaps:
        new_card = by_name[new]
        gain = int(new_card.game_changer) - int(in_deck[old].game_changer if old in in_deck else False)
        denial = bool(current.mass_land_denial) or is_mass_land_denial(new_card)
        floor = bracket_floor(len(current.game_changers) + gain, int(denial))
        if new_card.game_changer:
            notes[new] = f"a Game Changer: the deck would have {len(current.game_changers) + gain}, and play at Bracket {floor} or higher"
        elif is_mass_land_denial(new_card):
            notes[new] = f"mass land denial: the deck would play at Bracket {floor} or higher"
        elif gain < 0 and floor < current.floor:
            notes[new] = f"drops a Game Changer: the deck could play at Bracket {floor}"
    return notes


def _effect(deltas: list[float]) -> Effect:
    n = len(deltas)
    mean = sum(deltas) / n
    variance = sum((d - mean) ** 2 for d in deltas) / (n - 1) if n > 1 else 0.0
    return Effect(round(mean, 2), round(math.sqrt(variance / n), 2))


def _swapped(deck: Deck, replacements: dict[int, Card], commanders: dict[int, Card] | None = None) -> Deck:
    main = [replacements.get(i, card) for i, card in enumerate(deck.main)]
    return replace(deck, main=main, commanders=[(commanders or {}).get(i, c) for i, c in enumerate(deck.commanders)])


def _deltas(deck: Deck, changed: Deck, base: list[dict], games: int, turns: int, seed: int, play: bool, free: bool,
            only: set[int] | None = None) -> list[float]:
    """Per game, the changed deck's value minus the base deck's: the games outside `only` are known to be the same."""
    rerun = sorted(only) if only is not None else range(games)
    deltas = [0.0] * games
    for n in rerun:
        deltas[n] = game_value(play_game(changed, n, turns, seed, play, free)) - game_value(base[n])
    return deltas


def tune(deck: Deck, games: int = 500, turns: int = 8, seed: int = 0, candidates: list[Card] | None = None,
         on_the_play: bool = False, free_mulligan: bool | None = None, house: HouseRules = NO_HOUSE_RULES) -> TuningReport:
    if free_mulligan is None:
        free_mulligan = bool(deck.commanders)
    unplayable = unplayable_cards(deck)
    unreadable = {name for name, _, _ in unplayable}
    base = play_games(deck, games, turns, seed, on_the_play, free_mulligan)
    args = (base, games, turns, seed, on_the_play, free_mulligan)
    seen_in: dict[str, set[int]] = {}
    cast_in: Counter = Counter()
    for n, run in enumerate(base):
        for name in run["seen"]:
            seen_in.setdefault(name, set()).add(n)
        cast_in.update(run["cast"].keys())

    slots: dict[str, list[int]] = {}
    for i, card in enumerate(deck.main):
        if not is_land(card):
            slots.setdefault(card.name, []).append(i)
    impacts = []
    for name, seen in seen_in.items():
        in_main = slots.get(name, [])
        in_command = [i for i, c in enumerate(deck.commanders) if c.name == name]
        if not in_main and not in_command:
            continue
        changed = _swapped(deck, {i: BLANK for i in in_main}, {i: BLANK for i in in_command})
        effect = _effect([-d for d in _deltas(deck, changed, *args, only=seen)])
        rate = cast_in[name] / len(seen)
        note = "rarely cast when drawn" if rate < DEAD_WEIGHT else ""
        if name in unreadable:
            note = (note + "; " if note else "") + "text the engine can't read"
        impacts.append(CardImpact(name, len(in_main) + len(in_command), effect, round(len(seen) / games, 3), round(rate, 3), note))
    for name, indexes in slots.items():  # never drawn in any game: no evidence either way
        if name not in seen_in:
            impacts.append(CardImpact(name, len(indexes), Effect(0.0, 0.0), 0.0, 0.0, "never drawn in these games"
                                      + ("; text the engine can't read" if name in unreadable else "")))
    impacts.sort(key=lambda c: (c.value.delta / c.copies, c.name))

    baseline = sum(game_value(run) for run in base) / games
    legal, skipped = [], []
    for card in candidates or []:
        problem = candidate_problem(deck, card, house)
        (skipped.append((card.name, problem)) if problem else legal.append(card))
    swaps = _swap_candidates(deck, impacts, legal, seen_in, *args)
    return TuningReport(games, turns, round(baseline, 2), impacts, _land_sweep(deck, impacts, *args), swaps, skipped,
                        unplayable=unplayable, candidate_unplayable={card.name: lines[0] for card in legal if (lines := unsupported_lines(card))},
                        bracket=analyze(deck) if deck.commanders else None,
                        swap_notes=_bracket_notes(deck, swaps, legal) if deck.commanders else {}, mana_base=_mana_base(deck, base, turns))


def _mana_base(deck: Deck, base: list[dict], turns: int) -> ManaBase | None:
    """The deck's mana base analysis, with how often the goldfish games held a spell stuck on colors on turns 3 and 5."""
    mana_base = analyze_mana_base(deck)
    if mana_base:
        mana_base.stuck = {turn: sum(run["stuck"][turn - 1] for run in base) / len(base) for turn in (3, 5) if turn <= turns and base}
    return mana_base


def _land_sweep(deck: Deck, impacts: list[CardImpact], *args) -> dict[int, Effect]:
    """+k: the k weakest drawn nonland cards become the deck's most played basic land; -k: k lands become extra copies of
    a typical (median) card, which a singleton deck could not do but which prices a land slot against an average spell."""
    lands = Counter(c.name for c in deck.main if is_land(c))
    in_main = {i.name: [n for n, c in enumerate(deck.main) if c.name == i.name] for i in impacts if i.seen_rate}
    ranked = [i for i in impacts if in_main.get(i.name)]  # weakest first
    if not lands or not ranked:
        return {}
    land = next(c for c in deck.main if c.name == lands.most_common(1)[0][0])
    typical = next(c for c in deck.main if c.name == ranked[len(ranked) // 2].name)
    weak = [n for i in ranked for n in in_main[i.name]]
    land_slots = [n for n, c in enumerate(deck.main) if is_land(c)]
    out: dict[int, Effect] = {}
    for k in (1, 2, 3):
        if len(weak) >= k:
            out[k] = _effect(_deltas(deck, _swapped(deck, {n: land for n in weak[:k]}), *args))
        if len(land_slots) > k + 20:
            out[-k] = _effect(_deltas(deck, _swapped(deck, {n: typical for n in land_slots[:k]}), *args))
    return dict(sorted(out.items()))


def _swap_candidates(deck: Deck, impacts: list[CardImpact], candidates: list[Card], seen_in: dict[str, set[int]], *args):
    """Each candidate takes the place of the weakest card that isn't a commander; the effect is the change in value."""
    base, games, turns, seed, play, free = args
    in_main = {c.name: [i for i, card in enumerate(deck.main) if card.name == c.name] for c in deck.main}
    weakest = next((imp for imp in impacts if imp.seen_rate and in_main.get(imp.name)), None)
    if weakest is None:
        return []
    out = []
    slot = in_main[weakest.name][0]
    for card in candidates:
        deltas = _deltas(deck, _swapped(deck, {slot: card}), *args, only=seen_in.get(weakest.name, set()))
        out.append((card.name, weakest.name, _effect(deltas)))
    return sorted(out, key=lambda t: -t[2].delta)


def _plusminus(effect: Effect) -> str:
    return f"{effect.delta:+.2f} ±{effect.error:.2f}" + ("" if effect.clear else "  (within noise)")


def format_tuning(report: TuningReport, *, bracket: bool = True, unplayable: bool = True, mana_base: bool = True) -> str:
    """The report as text. A caller that prints the Bracket, the cards the engine can't play or the mana base itself (`analyze`) turns
    them off here so they are not said twice."""
    lines = [f"{report.games} games, {report.turns} turns. Average game value {report.baseline} "
             "(mana spent on spells + damage dealt by the last turn).",
             *([f"Bracket: {report.bracket.summary()}."] if report.bracket and bracket else []),
             *([unplayable_note(report.unplayable, "The deck", "The goldfish does not read card text, so these numbers do not change, "
                                "but a matchup run would play these cards without that text.")] if report.unplayable and unplayable else []), "",
             "Per card, weakest first: what the card adds per game, replayed with the card as a blank.",
             "card                                  copies  adds per game        seen  cast if seen  note"]
    for card in report.cards:
        lines.append(f"{card.name[:36]:<36}  {card.copies:>6}  {_plusminus(card.value):<20}  {card.seen_rate:>4.0%}  "
                     f"{card.cast_when_seen:>11.0%}  {card.note}")
    if report.lands:
        lines += ["", "Land count (change in lands -> change in value):"]
        lines += [f"  {k:+d} lands: {_plusminus(effect)}" for k, effect in report.lands.items()]
    if report.mana_base and mana_base:
        lines += ["", format_mana_base(report.mana_base)]
    if report.swaps:
        lines += ["", "Swaps (best first): the card replaces the weakest card in the deck."]
        lines += [f"  {new} for {old}: {_plusminus(effect)}"
                  + (f"  [{report.swap_notes[new]}]" if new in report.swap_notes else "")
                  + (f"  [the engine can't read: {report.candidate_unplayable[new][:60]}]" if new in report.candidate_unplayable else "")
                  for new, old, effect in report.swaps]
    if report.suggestions:
        lines += ["", *_suggestion_lines(report)]
    shown = {suggestion.card for suggestion in report.suggestions}
    if skipped := [(name, why) for name, why in report.skipped if name not in shown]:
        lines += ["", "Not tried: " + ", ".join(f"{name} ({why})" for name, why in skipped)]
    return "\n".join(lines)


COMBOS_SHOWN = 3  # the combos listed under each suggested card; the rest are counted


def _suggestion_lines(report: TuningReport) -> list[str]:
    """The cards one away from a combo, each with the combos it would complete and what they produce. The swap number is the goldfish's,
    which cannot see a combo, so it is only a side note; whether the engine plays the combo whole is what the deck's report is about."""
    effects = {new: effect for new, _, effect in report.swaps}
    why_not = dict(report.skipped)
    cannot = {name for name, _, _ in report.unplayable}
    lines = ["Combos one card away (Commander Spellbook). The swap number is the goldfish's, which cannot see what a combo does:"]
    for suggestion in report.suggestions:
        n = len(suggestion.combos)
        if suggestion.card in effects:
            tried = f"swap {_plusminus(effects[suggestion.card])}"
        else:
            tried = f"not tried: {why_not.get(suggestion.card, 'no swap was measured')}"
        lines.append(f"  {suggestion.card}: completes {n} combo{'s' if n != 1 else ''}; {tried}")
        for combo in suggestion.combos[:COMBOS_SHOWN]:
            others = [name for name in combo.cards if name != suggestion.card]
            makes = ", ".join(combo.produces[:3]) + (", ..." if len(combo.produces) > 3 else "")
            needs = f" (needs {', '.join(combo.requires)})" if combo.requires else ""
            stuck = sorted({name for name in others if name in cannot} | ({suggestion.card} if suggestion.card in report.candidate_unplayable else set()))
            lines.append(f"    with {' + '.join(others)}{needs}: {makes} ({combo.tag_name}, {combo.popularity:,} decks)"
                         + (f"  [the engine can't play {', '.join(stuck)}]" if stuck else ""))
        if n > COMBOS_SHOWN:
            lines.append(f"    and {n - COMBOS_SHOWN} more")
    return lines


def main(argv: list[str], source=None, spellbook: SpellbookSource | None = None) -> int:
    import argparse

    from .cards import BulkSource, CardNotFound, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("decklist")
    parser.add_argument("--games", type=int, default=500)
    parser.add_argument("--turns", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--play", action="store_true", help="be on the play (no draw on turn 1)")
    parser.add_argument("--try", dest="candidates", action="append", default=[], metavar="CARD", help="a card to test in the weakest slot")
    parser.add_argument("--suggest-combos", type=int, nargs="?", const=10, default=None, metavar="N",
                        help="also try the N cards (default 10) that would complete the most combos the deck is one card from (Commander Spellbook)")
    add_house_rules_arguments(parser)
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv[1:])
    source = source or BulkSource(args.bulk)
    house = house_rules(args)
    with open(args.decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), source)
    try:
        candidates = [source.get(name) for name in args.candidates]
    except CardNotFound as error:
        print(f"unknown card: {error}", file=sys.stderr)
        return 2
    suggestions: list[ComboSuggestion] = []
    unknown: list[tuple[str, str]] = []
    if args.suggest_combos is not None:
        if not deck.commanders:
            print("Error: --suggest-combos needs a Commander deck (Commander Spellbook knows no other)", file=sys.stderr)
            return 2
        try:
            found = (spellbook or SpellbookSource()).find(deck)
        except OSError as error:
            print(f"Error: Commander Spellbook could not be reached and the cache has no answer for this deck ({error})", file=sys.stderr)
            return 2
        suggestions = combo_suggestions(deck, found.almost, args.suggest_combos)
        for suggestion in suggestions:
            if any(card.name == suggestion.card for card in candidates):
                continue
            try:
                candidates.append(source.get(suggestion.card))
            except CardNotFound:
                unknown.append((suggestion.card, "not in the card data"))
    report = tune(deck, args.games, args.turns, args.seed, candidates, args.play, house=house)
    report.suggestions = suggestions
    report.skipped += unknown
    tried = [card for card in candidates if not any(name == card.name for name, _ in report.skipped)]
    if note := house.note([deck, Deck([], tried, [])], format_of([deck])):
        print(note)
    print(format_tuning(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
