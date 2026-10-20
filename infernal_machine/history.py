"""Keep an analysis's numbers, and show what changed after an edit (issue #411).

    python -m infernal_machine.analyze DECKLIST [OPPONENT ...] --save run.json      # keep this run's numbers
    python -m infernal_machine.analyze DECKLIST [OPPONENT ...] --since run.json     # ... and say what moved against an earlier run

`analyze` takes minutes, and asking "did my edit help" meant reading two long reports. A saved run holds the deck (its cards and copies),
the settings, each part's numbers and its text. Against it, a new run adds a "What changed" section: the cards that changed, the Bracket,
the mana base, the goldfish numbers and the win rate against each opponent, each with before, after and, where the games give an error
bar, whether the change is outside it. Differences between two runs of games are partly noise: a rate is called outside noise only when the
95% interval of the difference between the two (two independent proportions) leaves out zero, and numbers without an error bar (an average
damage) are shown without a verdict.

A part is not played again when the saved run has it for the same deck, the same settings (games, turns, seed, the candidates tried, the
opponents' decks) and the same version of this file: its numbers and text are reused ("reused from run.json"). That is what makes a
re-run after changing only the opponents or the matchup games quick; a changed card changes every part, so nothing is reused then.
`--no-reuse` plays everything again and still compares.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Iterable
from typing import Any

from .cards import Deck
from .sequential import Z

PART_TITLES = {"playability": "playability", "bracket": "Commander Bracket", "manabase": "mana base", "goldfish": "goldfish", "tuning": "tuning", "matchups": "matchups"}
VERSION = 1  # of the snapshot's layout: a saved run of another version is neither compared nor reused


def fingerprint(deck: Deck) -> dict[str, int]:
    """The deck as copies of each card, commanders marked: {"Sol Ring": 1, "commander: Atraxa": 1}."""
    counts: Counter[str] = Counter(c.name for c in deck.main)
    counts.update(f"commander: {c.name}" for c in deck.commanders)
    return dict(sorted(counts.items()))


def part_settings(part: str, settings: dict, opponents: dict[str, Deck] | None = None) -> dict:
    """What a part's numbers depend on besides the deck: if these are equal in two runs, the part would come out the same."""
    if part in ("playability", "bracket", "manabase"):
        return {}
    base = {"sim_games": settings["sim_games"], "turns": settings["turns"], "seed": settings["seed"]}
    if part == "goldfish":
        return base
    if part == "tuning":
        return {**base, "candidates": sorted(settings.get("candidates", []))}
    return {"games": settings["games"], "pod": settings["pod"], "seed": settings["seed"],
            "opponents": {name: fingerprint(deck) for name, deck in sorted((opponents or {}).items())}}


def snapshot(name: str, deck: Deck, settings: dict, sections: dict[str, dict], opponents: dict[str, Deck] | None = None) -> dict:
    """A run's record. `sections` maps a part to {"title", "body", "code", "data"} (the numbers)."""
    return {"version": VERSION, "name": name, "deck": fingerprint(deck), "settings": settings,
            "parts": {part: {"settings": part_settings(part, settings, opponents), **section} for part, section in sections.items()}}


def save(path: str, record: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1, sort_keys=True)
        f.write("\n")


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    if record.get("version") != VERSION:
        raise ValueError(f"{path} was saved by another version of this tool (layout {record.get('version')}, this is {VERSION})")
    return record


def reusable(old: dict | None, part: str, deck: Deck, settings: dict, opponents: dict[str, Deck] | None = None) -> dict | None:
    """The saved section for `part` if the deck and the part's settings are what they were, else None."""
    if not old or old.get("deck") != fingerprint(deck):
        return None
    saved = old.get("parts", {}).get(part)
    if saved is None or saved.get("settings") != part_settings(part, settings, opponents):
        return None
    return saved


# --- comparing two runs ---------------------------------------------------------------------------------------------------------------

def proportion_change(before: float, n_before: int, after: float, n_after: int) -> tuple[float, bool]:
    """(the change, whether it is outside noise) for two rates, each from its own games: the interval of the difference of two
    independent proportions leaves out zero."""
    if not n_before or not n_after:
        return after - before, False
    error = math.sqrt(before * (1 - before) / n_before + after * (1 - after) / n_after)
    change = after - before
    if error == 0:
        return change, change != 0
    return change, abs(change) > Z * error


def _cards_changed(old: dict[str, int], new: dict[str, int]) -> str:
    removed = {name: n for name, n in sorted((Counter(old) - Counter(new)).items())}
    added = {name: n for name, n in sorted((Counter(new) - Counter(old)).items())}
    if not removed and not added:
        return "no card changed"
    show = lambda sign, cards: [f"{sign}{n} {name.removeprefix('commander: ')}" + (" (commander)" if name.startswith("commander: ") else "") for name, n in cards.items()]  # noqa: E731
    return ", ".join(show("-", removed) + show("+", added))


def _data(old: dict, new: dict, part: str, reused: set[str]) -> tuple[dict | None, dict | None]:
    """The two runs' numbers for a part, or nothing when the new run took the part from the old one."""
    if part in reused:
        return None, None
    return old.get(part, {}).get("data"), new.get(part, {}).get("data")


def _row(label: str, before: str, after: str, change: str, verdict: str = "") -> str:
    return f"{label:<30} {before:>9} {after:>9} {change:>9}  {verdict}"


def _rate_row(label: str, before: float, n_before: int, after: float, n_after: int) -> str:
    change, outside = proportion_change(before, n_before, after, n_after)
    return _row(label, f"{before:.1%}", f"{after:.1%}", f"{change * 100:+.1f}", "outside noise" if outside else "within noise")


def compare(old: dict, new: dict, source: str = "the earlier run") -> str:
    """The "What changed" text: `old` and `new` are snapshots of the same deck name or of an edited one."""
    lines = [f"Compared with {source}: {_cards_changed(old['deck'], new['deck'])}."]
    if old.get("name") != new.get("name"):
        lines.append(f"(The earlier run was of {old.get('name')}.)")
    differing = [key for key in ("games", "sim_games", "turns", "seed", "pod") if old.get("settings", {}).get(key) != new.get("settings", {}).get(key)]
    if differing:
        lines.append("The settings differ (" + ", ".join(f"{k} {old['settings'].get(k)} -> {new['settings'].get(k)}" for k in differing)
                     + "), so numbers that depend on them are not directly comparable.")
    parts_old, parts_new = old.get("parts", {}), new.get("parts", {})
    reused = set(new.get("reused", []))  # parts taken from the earlier run: nothing to compare

    a, b = _data(parts_old, parts_new, "playability", reused)
    if a and b:
        before, after = {c["name"] for c in a["unplayable"]}, {c["name"] for c in b["unplayable"]}
        in_old, in_new = set(old["deck"]), set(new["deck"])  # a card taken out of the deck did not become playable, and an added one did not break
        now_playable, now_blocked = sorted((before - after) & in_new), sorted((after - before) & in_old)
        extra = ([f"now playable: {', '.join(now_playable)}"] if now_playable else []) + ([f"no longer: {', '.join(now_blocked)}"] if now_blocked else [])
        lines.append(f"Playable cards: {a['playable']} of {a['cards']} -> {b['playable']} of {b['cards']}" + (f" ({'; '.join(extra)})" if extra else "") + ".")

    a, b = _data(parts_old, parts_new, "bracket", reused)
    if a and b:
        gained = sorted(set(b["game_changers"]) - set(a["game_changers"]))
        lost = sorted(set(a["game_changers"]) - set(b["game_changers"]))
        text = f"Bracket: {a['floor']} -> {b['floor']}" if a["floor"] != b["floor"] else f"Bracket: still {b['floor']} or higher"
        extra = ([f"new Game Changers: {', '.join(gained)}"] if gained else []) + ([f"no longer: {', '.join(lost)}"] if lost else [])
        lines.append(text + (f" ({'; '.join(extra)})" if extra else "") + ".")

    a, b = _data(parts_old, parts_new, "manabase", reused)
    if a and b:
        moved = []
        for color in sorted(set(a["colors"]) | set(b["colors"])):
            x, y = a["colors"].get(color), b["colors"].get(color)
            if x != y:
                moved.append(f"{color}: sources {x['have'] if x else 0} -> {y['have'] if y else 0}, short by {x['short'] if x else 0} -> {y['short'] if y else 0}")
        lines.append("Mana base: " + ("; ".join(moved) if moved else "no color's sources or shortfall changed") + f" ({a['lands']} -> {b['lands']} lands).")

    a, b = _data(parts_old, parts_new, "goldfish", reused)
    if a and b:
        last = str(min(a["turns"], b["turns"]))
        mid = str(max(1, int(last) // 2))
        rows = [_rate_row("mulligan rate", a["mulligan_rate"], a["games"], b["mulligan_rate"], b["games"]),
                _row("opening lands", f"{a['opening_lands']:.2f}", f"{b['opening_lands']:.2f}", f"{b['opening_lands'] - a['opening_lands']:+.2f}"),
                _row("mana spent / available", f"{a['mana_efficiency']:.0%}", f"{b['mana_efficiency']:.0%}", f"{(b['mana_efficiency'] - a['mana_efficiency']) * 100:+.1f}")]
        if a.get("on_curve") is not None and b.get("on_curve") is not None:
            rows.append(_row("on curve", f"{a['on_curve']:.0%}", f"{b['on_curve']:.0%}", f"{(b['on_curve'] - a['on_curve']) * 100:+.1f}"))
        for turn in (mid, last):
            if turn in a["land_drops"] and turn in b["land_drops"]:
                rows.append(_rate_row(f"land drops through turn {turn}", a["land_drops"][turn], a["games"], b["land_drops"][turn], b["games"]))
        if last in a["damage"] and last in b["damage"]:
            rows.append(_row(f"damage by turn {last}", f"{a['damage'][last]:.1f}", f"{b['damage'][last]:.1f}", f"{b['damage'][last] - a['damage'][last]:+.1f}"))
        lines += ["", "Goldfish:", _row("", "before", "after", "change"), *rows]

    a, b = _data(parts_old, parts_new, "matchups", reused)
    if a and b:
        rows = []
        for opponent in sorted(set(a["opponents"]) & set(b["opponents"])):
            x, y = a["opponents"][opponent], b["opponents"][opponent]
            if x["games"] and y["games"]:
                rows.append(_rate_row(opponent[:30], x["wins"] / x["games"], x["games"], y["wins"] / y["games"], y["games"]))
        new_only = sorted(set(b["opponents"]) - set(a["opponents"]))
        if rows:
            lines += ["", "Win rate against each opponent present in both runs:", _row("", "before", "after", "change"), *rows]
        if new_only:
            lines.append(f"Not in the earlier run: {', '.join(new_only)}.")
        if rows:
            lines.append(f"{sum(r.endswith('outside noise') for r in rows)} of {len(rows)} win rates moved outside noise.")

    a, b = _data(parts_old, parts_new, "tuning", reused)
    if a and b:
        lines += ["", f"Tuning: the deck's average game value {a['baseline']:.1f} -> {b['baseline']:.1f}"
                      f" (no error bar kept: read it with the numbers above)."]
    if reused:
        names = [PART_TITLES.get(part, part) for part in ("bracket", "manabase", "goldfish", "tuning", "matchups") if part in reused]
        lines.append(f"Not compared (taken from the earlier run, so the same): {', '.join(names)}.")
    return "\n".join(lines).rstrip()


def parts_reused(analysis_reused: Iterable[str]) -> str:
    names = list(analysis_reused)
    return f"Reused from the earlier run (same deck and settings): {', '.join(names)}." if names else ""


def jsonable(value: Any) -> Any:
    """`value` as JSON would keep it (dict keys become strings): the numbers of a fresh run look the same as a loaded one's."""
    return json.loads(json.dumps(value))
