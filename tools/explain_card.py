"""How the engine read a card, and the misparse audit (issue #478).

    python tools/explain_card.py "Fearless Fledgling" ["Another Card" ...] [--bulk .cache/oracle_bulk.json]
    python tools/explain_card.py --audit [--bulk .cache/oracle_bulk.json] [--limit N]

The first prints each ability the way the engine holds it, beside the Oracle text: the event, the condition, each effect with its fields,
what it is bound to (the source, the permanent that set the trigger off, ...) and what it targets, and the lines it did not understand.
Read it when a card does something odd in a game: a wrong reading shows here before it shows anywhere else.

The second runs the audit rules (`infernal_machine/explain.py`) over every card in the card file and lists what they flag; it exits 1 if
anything is flagged, so it can gate a pull request. "Fully playable" means parsed, not parsed correctly; the rules are how that gap is
closed one kind of mistake at a time. It reads the card file only (offline).
"""

from __future__ import annotations

import argparse
import io
import os
import sys

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import BulkSource, Card, CardNotFound  # noqa: E402
from infernal_machine.explain import audit, explain  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cards", nargs="*", metavar="CARD", help="card names to explain")
    parser.add_argument("--audit", action="store_true", help="run the audit rules over every card in the card file")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json", help="the card file")
    parser.add_argument("--limit", type=int, default=0, help="with --audit, stop listing after this many findings (0: all)")
    args = parser.parse_args(argv)
    if bool(args.cards) == args.audit:
        parser.error("give card names to explain, or --audit")
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    source = BulkSource(args.bulk)
    if args.audit:
        import json

        with open(args.bulk, encoding="utf-8") as f:
            cards = [Card.from_dict(d) for d in json.load(f)["cards"].values()]
        findings = [finding for card in cards for finding in audit(card)]
        for finding in findings[:args.limit or None]:
            print(finding)
        print(f"{len(findings)} finding{'s' if len(findings) != 1 else ''} in {len(cards)} cards.")
        return 1 if findings else 0
    for i, name in enumerate(args.cards):
        try:
            card = source.get(name)
        except CardNotFound:
            print(f"no card named {name!r} in {args.bulk}", file=sys.stderr)
            return 2
        print(("\n" + "-" * 72 + "\n" if i else "") + explain(card))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
