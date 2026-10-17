"""A small saved gauntlet: decks to play against when you name no opponents (#395).

    python -m infernal_machine.gauntlet [--list] [--max-bracket N]
    python -m infernal_machine.gauntlet --check            # the saved Bracket floors still match the decks (needs the card file)
    python -m infernal_machine.gauntlet --add DECKLIST     # copy a decklist in and save its Bracket floor

`examples/gauntlet.json` lists the decks (`file` is relative to `examples/`), each with the Bracket floor of its cards (`brackets.py`)
and its commander. `matchup`, `analyze`, `compare` and `impact` use it when they are given no opponents, and their `--max-bracket`
(or `--max-bracket` here) picks among the saved decks without loading any of them. The five Secrets of Strixhaven precons are the
start; every one plays at Bracket 1, so the gauntlet cannot yet separate a Bracket 1 table from a Bracket 3 one: `--add` is how a
stronger deck (exported from a deck site and turned into a decklist by `tools/import_deck.py`) joins it.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
from dataclasses import dataclass

EXAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
MANIFEST = os.path.join(EXAMPLES, "gauntlet.json")


@dataclass(frozen=True)
class Entry:
    name: str
    path: str  # absolute
    bracket: int  # the lowest Bracket the deck can be played at
    commander: str


def load(manifest: str = MANIFEST) -> list[Entry]:
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    base = os.path.dirname(os.path.abspath(manifest))
    return [Entry(d["name"], os.path.join(base, d["file"]), int(d["bracket"]), d.get("commander", "")) for d in data["decks"]]


def opponents(max_bracket: int | None = None, manifest: str = MANIFEST) -> list[Entry]:
    """The saved decks that can be played at Bracket `max_bracket` or lower (all of them without a limit)."""
    return [e for e in load(manifest) if max_bracket is None or e.bracket <= max_bracket]


def opponent_paths(given: list[str], max_bracket: int | None = None, manifest: str = MANIFEST) -> list[str]:
    """The decklists to play against: the ones named, or, with none named, the saved gauntlet (within `max_bracket`, if there is one).
    Says so on standard error when it falls back to the gauntlet; exits if nothing is left."""
    if given:
        return given
    chosen = opponents(max_bracket, manifest)
    if not chosen:
        raise SystemExit(f"No saved gauntlet deck is playable at Bracket {max_bracket} or lower.")
    limit = f" at Bracket {max_bracket} or lower" if max_bracket is not None else ""
    print(f"No opponents given: using the saved gauntlet ({len(chosen)} deck{'s' if len(chosen) != 1 else ''}{limit}).", file=sys.stderr)
    return [e.path for e in chosen]


def check(manifest: str = MANIFEST, bulk: str = ".cache/oracle_bulk.json") -> list[str]:
    """What is wrong with the manifest: a missing file, or a Bracket floor or commander that is not what the deck's cards say."""
    from .brackets import analyze
    from .cards import BulkSource, load_deck

    problems = []
    source = BulkSource(bulk)
    for entry in load(manifest):
        if not os.path.exists(entry.path):
            problems.append(f"{entry.name}: {entry.path} does not exist")
            continue
        with open(entry.path, encoding="utf-8") as f:
            deck = load_deck(f.read(), source)
        floor = analyze(deck).floor
        if floor != entry.bracket:
            problems.append(f"{entry.name}: saved at Bracket {entry.bracket}, its cards say {floor}")
        names = ", ".join(c.name for c in deck.commanders)
        if names != entry.commander:
            problems.append(f"{entry.name}: saved commander {entry.commander!r}, the deck has {names!r}")
    return problems


def add(decklist: str, manifest: str = MANIFEST, bulk: str = ".cache/oracle_bulk.json", name: str | None = None) -> Entry:
    """Copy a decklist into `examples/gauntlet/` and save it with its Bracket floor and commander."""
    from .brackets import analyze
    from .cards import BulkSource, load_deck

    with open(decklist, encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(bulk))
    if not deck.commanders:
        raise SystemExit("A gauntlet deck needs a commander (the gauntlet is for Commander tables).")
    base = os.path.dirname(os.path.abspath(manifest))
    name = name or os.path.splitext(os.path.basename(decklist))[0]
    relative = f"gauntlet/{name}.txt"
    with open(manifest, encoding="utf-8") as f:
        data = json.load(f)
    if any(d["name"] == name for d in data["decks"]):
        raise SystemExit(f"The gauntlet already has a deck called {name}.")
    os.makedirs(os.path.join(base, "gauntlet"), exist_ok=True)
    shutil.copyfile(decklist, os.path.join(base, relative))
    entry = {"name": name, "file": relative, "bracket": analyze(deck).floor, "commander": ", ".join(c.name for c in deck.commanders)}
    data["decks"].append(entry)
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return Entry(name, os.path.join(base, relative), entry["bracket"], entry["commander"])


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--list", action="store_true", help="list the saved decks (the default)")
    parser.add_argument("--max-bracket", type=int, metavar="N", help="only the decks playable at Bracket N or lower")
    parser.add_argument("--check", action="store_true", help="check the saved Bracket floors and commanders against the decks")
    parser.add_argument("--add", metavar="DECKLIST", help="add a decklist to the gauntlet")
    parser.add_argument("--name", help="with --add, the name to save it under (default: the file's)")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    if args.add:
        entry = add(args.add, bulk=args.bulk, name=args.name)
        print(f"Added {entry.name} (Bracket {entry.bracket}, commander {entry.commander}).")
        return 0
    if args.check:
        problems = check(bulk=args.bulk)
        for problem in problems:
            print(problem)
        print(f"{len(problems)} problem(s) in the gauntlet." if problems else f"The gauntlet's {len(load())} decks match their cards.")
        return 1 if problems else 0
    for entry in opponents(args.max_bracket):
        print(f"Bracket {entry.bracket}  {entry.name:<28} {entry.commander}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
