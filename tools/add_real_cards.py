"""Add cards' real Oracle text to the test fixture, from the cached Commander pool (issue #809).

    python tools/add_real_cards.py NAME [NAME ...] [--pool .cache/commander_pool.json]

The tests run offline, so a test that names real cards (`REAL[name]`, `wording_unlocked`) needs their text in
`tests/real_oracle_texts.json`. This copies each named card's text from the pool into it, as the fixture writes it, and leaves a card
already there alone. A name not in the pool, or a card with more than one face (the fixture holds single faces), is refused, and
then nothing is written.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "real_oracle_texts.json"
FIELDS = ("name", "mana_cost", "type_line", "oracle_text", "power", "toughness", "colors")


def entry(data: dict) -> dict:
    """The fixture's record of a card from its Scryfall data."""
    record = {field: data.get(field) for field in FIELDS}
    record["colors"] = list(data.get("colors") or [])
    if data.get("produced_mana"):
        record["produced_mana"] = list(data["produced_mana"])
    return record


def add(names: list[str], pool: list[dict], fixture: dict) -> tuple[list[str], list[str]]:
    """Add the named cards to `fixture` (in place): (the names added, the problems). With a problem, nothing is added."""
    by_name = {data["name"]: data for data in pool}
    have = {card["name"] for card in fixture["cards"] + fixture.get("unsupported_cards", [])}
    problems, records = [], []
    for name in dict.fromkeys(names):
        data = by_name.get(name)
        if data is None:
            problems.append(f"{name}: not in the pool")
        elif "card_faces" in data:
            problems.append(f"{name}: has more than one face, which the fixture does not hold")
        elif name not in have:
            records.append(entry(data))
    if problems:
        return [], problems
    fixture["cards"].extend(records)
    return [record["name"] for record in records], []


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="+")
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    args = parser.parse_args(argv)
    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    added, problems = add(args.names, pool, fixture)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    FIXTURE.write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"added {len(added)} card(s): {', '.join(added) or '(all already there)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
