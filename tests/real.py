"""The real Oracle texts in `real_oracle_texts.json` as cards (issues #25, #50 and #97), importable by any test."""

import json
from pathlib import Path

from infernal_machine.cards import Card, _mana_value

DATA = json.loads((Path(__file__).parent / "real_oracle_texts.json").read_text(encoding="utf-8"))
REAL = {c["name"]: Card(name=c["name"], mana_cost=c["mana_cost"], type_line=c["type_line"], oracle_text=c["oracle_text"],
                        power=c["power"], toughness=c["toughness"], colors=tuple(c["colors"]),
                        cmc=_mana_value(c["mana_cost"]))
        for c in DATA["cards"]}
