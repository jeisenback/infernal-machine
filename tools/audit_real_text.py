"""Compare the engine's idea of card text with the real Oracle text (issues #25 and #50).

    python tools/audit_real_text.py [--bulk .cache/oracle_bulk.json]

Prints (1) the test cards that share a name with a real card but have different text, and which of them the engine
supports while the real card has lines it does not, and (2) how many well-known Commander cards the engine fully
supports. Run it from the repository root after refreshing the bulk data; a test card that reuses a real name with
invented text is easy to mistake for a verified one.
"""

from __future__ import annotations

import argparse
import glob
import importlib
import os
import re
import sys

sys.path.insert(0, os.getcwd())

from infernal_machine.cards import BulkSource, Card, CardNotFound  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402

STAPLES = """Sol Ring|Arcane Signet|Command Tower|Lightning Bolt|Counterspell|Swords to Plowshares|Path to Exile|Wrath of God|
Cultivate|Kodama's Reach|Rampant Growth|Farseek|Rhystic Study|Mystic Remora|Swiftfoot Boots|Lightning Greaves|Mind Stone|
Thought Vessel|Birds of Paradise|Llanowar Elves|Cyclonic Rift|Mana Drain|Demonic Tutor|Doom Blade|Go for the Throat|
Chaos Warp|Blasphemous Act|Toxic Deluge|Damnation|Pernicious Deed|Read the Bones|Brainstorm|Ponder|Preordain|Mulldrifter|
Solemn Simulacrum|Skullclamp|Sensei's Divining Top|Smothering Tithe|Doubling Season|Parallel Lives|Rancor|Clone|
Reflecting Pool|Exotic Orchard|Evolving Wilds|Blood Crypt|Breeding Pool|Misty Rainforest|Treetop Village|Mutavault|
Cabal Coffers|Gaea's Cradle|Reanimate|Animate Dead|Threaten|Gilded Lotus|Kaalia of the Vast|Edgar Markov""".replace("\n", "").split("|")


def normal(text: str) -> list[str]:
    text = re.sub(r"\s*\([^)]*\)", "", text or "").replace("−", "-").replace("—", "-")
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    args = parser.parse_args()
    source = BulkSource(args.bulk)
    index = source._load()

    differing = []
    for path in sorted(glob.glob("tests/test_*.py")):
        module = importlib.import_module("tests." + os.path.basename(path)[:-3])
        for variable, value in vars(module).items():
            if isinstance(value, Card) and value.oracle_text and value.name.lower() in index:
                real = index[value.name.lower()]
                if normal(value.oracle_text) != normal(real.oracle_text):
                    differing.append((value, real, f"{os.path.basename(path)}:{variable}"))
    print(f"{len(differing)} test cards have a real card's name but different text")
    risky = [(t, r, w) for t, r, w in differing if not unsupported_lines(t) and unsupported_lines(r)]
    print(f"{len(risky)} of them are fully supported while the real card has unsupported lines:")
    for test, real, where in risky:
        print(f"  - {test.name} ({where}): {unsupported_lines(real)[0][:100]}")

    unsupported = []
    for name in STAPLES:
        try:
            lines = unsupported_lines(source.get(name))
        except CardNotFound:
            print(f"  missing from the bulk data: {name}")
            continue
        if lines:
            unsupported.append((name, lines[0][:100]))
    print(f"\n{len(STAPLES) - len(unsupported)} of {len(STAPLES)} staples are fully supported; not:")
    for name, line in unsupported:
        print(f"  - {name}: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
