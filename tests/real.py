"""The real Oracle texts in `real_oracle_texts.json` as cards (issues #25, #50 and #97), importable by any test."""

import json
from pathlib import Path

from infernal_machine.cards import Card, _mana_value

DATA = json.loads((Path(__file__).parent / "real_oracle_texts.json").read_text(encoding="utf-8"))
REAL = {c["name"]: Card(name=c["name"], mana_cost=c["mana_cost"], type_line=c["type_line"], oracle_text=c["oracle_text"],
                        power=c["power"], toughness=c["toughness"], colors=tuple(c["colors"]),
                        cmc=_mana_value(c["mana_cost"]), produced_mana=tuple(c.get("produced_mana", ())),
                        prepare=(Card(name=c["prepare"]["name"], mana_cost=c["prepare"]["mana_cost"],
                                      cmc=_mana_value(c["prepare"]["mana_cost"]), type_line=c["prepare"]["type_line"],
                                      oracle_text=c["prepare"]["oracle_text"], colors=tuple(c["prepare"]["colors"]))
                                 if "prepare" in c else None))
        for c in DATA["cards"] + DATA.get("unsupported_cards", [])}  # the second list is on purpose: tests of what the report lists as missing
