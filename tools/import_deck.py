"""Turn a deck list you exported from Moxfield or Archidekt (or copied from anywhere) into a decklist file `load_deck` reads (#395).

    python tools/import_deck.py EXPORT.txt [-o deck.txt] [--check] [--bulk .cache/oracle_bulk.json]
    python tools/import_deck.py - < EXPORT.txt

It makes no network request: neither site offers a public API (Moxfield has none and turns bots away; Archidekt's open JSON is
unofficial and its terms forbid scripted requests), so the way in is the text each site lets you copy or download itself (Moxfield:
the deck's "Export" and then text; Archidekt: "Export", then text or CSV). Read:

- lines like `1 Sol Ring`, `1x Sol Ring (C21) 263`, `1x Sol Ring (c21) 263 [Ramp] ^Staples^ *F*`, with set codes, collector
  numbers, `[Category]` and `^Tag^` annotations and foil marks dropped (a duplicate card has its counts added up);
- the commander: a `Commander` section, a `*CMDR*` mark, or a `[Commander]` category (Archidekt writes `[Commander{top}]`);
- the sideboard (a `Sideboard` section, `SB:` lines); a Maybeboard, Considering or Tokens section is left out; with nothing marked as
  the commander, a 99-card list that ends with one card alone after the sideboard (where Moxfield puts it) takes that card for it;
- a CSV export with `Count` and `Name` columns (and `Board`, `Section` or `Category` if there is one).

It writes `Commander`, `Deck` and `Sideboard` sections, tells you what it dropped, and warns when a 100-card list has no commander.
With `--check` it also loads the deck from the card file (offline) and reports cards it can't find and the deck's Bracket floor.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.getcwd())

SKIPPED_SECTIONS = {"maybeboard", "considering", "tokens", "token", "acquire", "wishlist"}
SECTION_NAMES = {"commander": "commander", "commanders": "commander", "main": "main", "mainboard": "main", "deck": "main",
                 "sideboard": "side", "side": "side", "sb": "side"}
_ANNOTATIONS = re.compile(r"\s*(\^[^^]*\^|\[[^\]]*\])")  # ^Tag^ and [Category]
_SET_AND_NUMBER = re.compile(r"\s+\([A-Za-z0-9]{2,6}\)(?:\s+\S+)?\s*$")
_MARK = re.compile(r"\s*\*[A-Za-z]+\*")  # *F*, *E*, *CMDR*
_COUNT = re.compile(r"^(\d+)\s*x?\s+(\S.*)$", re.I)
_SIDE_PREFIX = re.compile(r"^SB:\s*", re.I)


class Imported:
    def __init__(self) -> None:
        self.commanders: dict[str, int] = {}
        self.main: dict[str, int] = {}
        self.side: dict[str, int] = {}
        self.dropped: list[str] = []  # what was left out, described
        self.assumed: list[str] = []  # what was guessed, described (the commander at the end of a Moxfield export)
        self.side_blocks: list[list[tuple[str, int]]] = []  # the cards of the sideboard, a list per paragraph

    def add(self, section: str, name: str, count: int) -> None:
        target = {"commander": self.commanders, "main": self.main, "side": self.side}[section]
        target[name] = target.get(name, 0) + count
        if section == "side":
            if not self.side_blocks:
                self.side_blocks.append([])
            self.side_blocks[-1].append((name, count))

    def break_side(self) -> None:
        """A blank line inside the sideboard: the next card starts a new paragraph."""
        if self.side_blocks and self.side_blocks[-1]:
            self.side_blocks.append([])

    def find_trailing_commander(self) -> None:
        """Moxfield's text export ends with the commander alone, after a blank line that follows the sideboard. With no commander marked, a
        99-card main deck and a last paragraph of one card, that card is taken for the commander (and the list says so)."""
        if self.commanders or sum(self.main.values()) != 99 or len(self.side_blocks) < 2:
            return
        last = self.side_blocks[-1]
        if len(last) != 1 or last[0][1] != 1:
            return
        name = last[0][0]
        del self.side[name]
        self.commanders[name] = 1
        self.assumed.append(f"Took {name} for the commander: it is the one card after the sideboard, where Moxfield lists it.")

    @property
    def total(self) -> int:
        return sum(self.commanders.values()) + sum(self.main.values())


def _categories(line: str) -> list[str]:
    """The category words of an Archidekt line: `[Commander{top}, Ramp]` gives commander and ramp."""
    words: list[str] = []
    for group in re.findall(r"\[([^\]]*)\]", line):
        words += [re.sub(r"\{.*?\}", "", part).strip().lower() for part in group.split(",")]
    return words


def _name(rest: str) -> str:
    rest = _MARK.sub("", _ANNOTATIONS.sub("", rest)).strip()
    return _SET_AND_NUMBER.sub("", rest).strip()


def parse_text(text: str) -> Imported:
    deck = Imported()
    section = "main"
    skipping = False
    seen_blank_after_main = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            seen_blank_after_main = section == "main" and bool(deck.main) and not skipping
            if section == "side":
                deck.break_side()
            continue
        if line.startswith("//") or line.startswith("#"):
            continue
        header = line.rstrip(":").strip().lower()
        if header in SKIPPED_SECTIONS:
            skipping = True
            continue
        if header in SECTION_NAMES:
            section, skipping, seen_blank_after_main = SECTION_NAMES[header], False, False
            continue
        if skipping:
            deck.dropped.append(line)
            continue
        if seen_blank_after_main:  # a blank line after the main deck starts the sideboard, as in `parse_decklist`
            section, seen_blank_after_main = "side", False
        where = section
        if _SIDE_PREFIX.match(line):
            line, where = _SIDE_PREFIX.sub("", line), "side"
        match = _COUNT.match(line)
        if not match:
            deck.dropped.append(line)
            continue
        count, rest = int(match[1]), match[2]
        categories = _categories(rest)
        if "*CMDR*" in rest or "commander" in categories or "commanders" in categories:
            where = "commander"
        elif any(c in SKIPPED_SECTIONS for c in categories):
            deck.dropped.append(line)
            continue
        elif "sideboard" in categories:
            where = "side"
        name = _name(rest)
        if name:
            deck.add(where, name, count)
    deck.find_trailing_commander()
    return deck


def parse_csv(text: str) -> Imported | None:
    """An exported CSV with Count and Name columns, or None if the text is not one."""
    first = next((line for line in text.splitlines() if line.strip()), "")
    header = [cell.strip().strip('"').lower() for cell in first.split(",")]
    if "count" not in header or "name" not in header:
        return None
    deck = Imported()
    for row in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        board = (row.get("board") or row.get("section") or row.get("category") or "").lower()
        if not row.get("name") or not row.get("count", "").isdigit():
            continue
        if board in SKIPPED_SECTIONS:
            deck.dropped.append(f"{row['count']} {row['name']}")
            continue
        deck.add({"commander": "commander", "commanders": "commander", "sideboard": "side", "side": "side"}.get(board, "main"),
                 _name(row["name"]), int(row["count"]))
    return deck


def parse(text: str) -> Imported:
    return parse_csv(text) or parse_text(text)


def render(deck: Imported) -> str:
    sections = [("Commander", deck.commanders), ("Deck", deck.main), ("Sideboard", deck.side)]
    return "\n\n".join(f"{title}\n" + "\n".join(f"{n} {name}" for name, n in cards.items()) for title, cards in sections if cards) + "\n"


def warnings(deck: Imported) -> list[str]:
    notes = list(deck.assumed)
    if not deck.commanders and deck.total in (99, 100):
        notes.append(f"{deck.total} cards and no commander: put yours under a Commander heading or mark it *CMDR* before using this as a Commander deck.")
    if deck.commanders and deck.total not in (99, 100):
        notes.append(f"A Commander deck has 100 cards with its commander; this one has {deck.total}.")
    if deck.dropped:
        shown = "; ".join(deck.dropped[:4]) + (f" and {len(deck.dropped) - 4} more" if len(deck.dropped) > 4 else "")
        notes.append(f"Left out {len(deck.dropped)} line(s) that are not part of the deck: {shown}.")
    return notes


def check(text: str, bulk: str) -> list[str]:
    """Load the written deck from the card file: the cards that can't be found, else its size and Bracket floor."""
    from infernal_machine.brackets import analyze
    from infernal_machine.cards import BulkSource, CardNotFound, load_deck

    try:
        loaded = load_deck(text, BulkSource(bulk))
    except CardNotFound as error:
        return [f"Check failed: {error}"]
    notes = [f"Check: {len(loaded.commanders)} commander(s) and {len(loaded.main)} other card(s) all found in {bulk}."]
    if loaded.commanders:
        report = analyze(loaded)
        notes.append(f"It can be played at Bracket {report.floor} or higher" + (f" ({', '.join(report.game_changers)} are Game Changers)." if report.game_changers else "."))
    return notes


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("export", help="the exported text or CSV file, or - for standard input")
    parser.add_argument("-o", "--output", help="write the decklist here (default: print it)")
    parser.add_argument("--check", action="store_true", help="load the deck from the card file and report what can't be found")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args(argv)
    text = sys.stdin.read() if args.export == "-" else open(args.export, encoding="utf-8-sig").read()
    deck = parse(text)
    if not deck.commanders and not deck.main:
        print("No cards found in that export.", file=sys.stderr)
        return 2
    out = render(deck)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"Wrote {args.output}: {deck.total} cards" + (f" and {sum(deck.side.values())} in the sideboard." if deck.side else "."), file=sys.stderr)
    else:
        print(out, end="")
    for note in warnings(deck) + (check(out, args.bulk) if args.check else []):
        print(note, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
