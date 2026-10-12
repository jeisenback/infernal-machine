"""Which rules-text templates are used, and which sentences two of them read (issue #287).

    python tools/template_audit.py [--pool .cache/commander_pool.json] [--top 40] [--json OUT.json]

`effects/outcomes.py` reads a sentence with the first template in `_TEMPLATES` that builds an effect from it, so the order of that
list is part of what the engine means. This runs `unsupported_lines` over every card of the Commander pool (the file the coverage
audit keeps) and reports two things the tests cannot see:

- templates that no sentence in the pool reached: dead after a wording change, or shadowed by an earlier, broader template after a
  reorder. Delete them, or move them, or find the card that needs them.
- sentences that more than one template reads. Where the effects differ, a reorder changes what the sentence means; where they are
  equal the order is only a convenience. The first template listed is the one that wins today.

It only reports; it never fails.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from typing import Any, Iterable

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import Card  # noqa: E402
from infernal_machine.effects import outcomes  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402


def audit(cards: Iterable[Card]) -> dict:
    """The templates that won no sentence, and the sentences read by more than one template, for these cards."""
    templates = outcomes._TEMPLATES
    readings: dict[str, list[tuple[int, Any]]] = {}  # sentence -> (template index, the effect it builds), in list order
    cards_with: collections.Counter = collections.Counter()  # sentence -> how many cards looked it up
    looked_up: set[str] = set()
    original = outcomes._template

    def spy(sentence: str) -> Any:
        looked_up.add(sentence)
        if sentence not in readings:
            found = []
            for index, (pattern, build) in enumerate(templates):
                match = pattern.fullmatch(sentence)
                effect = build(match) if match else None
                if effect is not None:
                    found.append((index, effect))
            readings[sentence] = found
        return original(sentence)

    outcomes._template = spy
    try:
        for card in cards:
            looked_up.clear()
            try:
                unsupported_lines(card)
            except Exception:  # a card the coverage audit reports as a crash is not this tool's business
                continue
            cards_with.update(looked_up)
    finally:
        outcomes._template = original
    won = {found[0][0] for found in readings.values() if found}
    ambiguous = []
    for sentence, found in readings.items():
        if len(found) > 1:
            winner, effect = found[0]
            ambiguous.append({"sentence": sentence, "cards": cards_with[sentence], "wins": winner,
                              "also": [index for index, _ in found[1:]],
                              "differs": any(other != effect for _, other in found[1:])})
    ambiguous.sort(key=lambda a: (-a["differs"], -a["cards"], a["sentence"]))
    return {"templates": len(templates), "sentences": len(readings),
            "unused": [{"index": i, "pattern": templates[i][0].pattern} for i in range(len(templates)) if i not in won],
            "ambiguous": ambiguous}


def render(result: dict, top: int = 40) -> str:
    """The audit as markdown."""
    lines = ["## Template audit", "",
             f"{result['templates']} templates; {result['sentences']:,} distinct sentences were looked up.", "",
             f"### Templates no sentence reached ({len(result['unused'])})", ""]
    lines += [f"- #{u['index']} `{u['pattern'][:140]}`" for u in result["unused"]] or ["None."]
    ambiguous = result["ambiguous"]
    differing = [a for a in ambiguous if a["differs"]]
    lines += ["", f"### Sentences read by more than one template ({len(ambiguous)}; {len(differing)} read differently)", "",
              "Where the effects differ, a reorder of `_TEMPLATES` changes what the sentence means. The winner is the first.", ""]
    if differing:
        lines += ["| cards | sentence | wins | also read by |", "| ---: | --- | ---: | --- |"]
        lines += [f"| {a['cards']} | {a['sentence'][:110]} | #{a['wins']} | {', '.join('#%d' % i for i in a['also'])} |"
                  for a in differing[:top]]
    else:
        lines.append("None read differently.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    from coverage_audit import fetch_pool  # next to this file when it is run as a script

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--json", help="also write the numbers here")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    result = audit(Card.from_scryfall(data) for data in fetch_pool(args.pool))
    print(render(result, args.top))
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
