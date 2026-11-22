"""Issues #844 and #845: "{N}, {T}: Search your library for a Rebel (or Mercenary) permanent card with mana value M or less, put it onto
the battlefield, then shuffle." (the Rebel and Mercenary searchers of Mercadian Masques), from the cards' real Oracle text. All eighteen
cards whose only gap it was are fully playable. Ramosian Sergeant ({3}, M = 2): of a Rebel with mana value 2, one with mana value 4 and a non-Rebel with mana value 1, only the
first is offered and put onto the battlefield; Lin Sivvi's X is the X paid (X = 3 finds the 3-drop Rebel, X = 1 doesn't)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import SEARCH_CARD_PROMPT, X_PROMPT, Permanent
from tests.helpers import lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Lin Sivvi, Defiant Hero", "Defiant Falcon", "Amrou Scout", "Ramosian Sergeant", "Ramosian Lieutenant", "Ramosian Captain",
         "Blightspeaker", "Ramosian Commander", "Ramosian Sky Marshal",
         "Cateran Enforcer", "Rathi Intimidator", "Cateran Kidnappers", "Cateran Slaver", "Rathi Fiend", "Cateran Brute", "Cateran Overlord",
         "Cateran Persuader", "Bog Glider"]
REBEL_2 = Card(name="Rebel Two", mana_cost="{1}{W}", cmc=2.0, type_line="Creature — Human Rebel", power="2", toughness="2")
REBEL_3 = Card(name="Rebel Three", mana_cost="{2}{W}", cmc=3.0, type_line="Creature — Human Rebel", power="3", toughness="3")
REBEL_4 = Card(name="Rebel Four", mana_cost="{3}{W}", cmc=4.0, type_line="Creature — Human Rebel", power="4", toughness="4")
ELF = Card(name="Elf One", mana_cost="{G}", cmc=1.0, type_line="Creature — Elf", power="1", toughness="1")

# The guards these tests are there to catch (python tools/mutate.py tests.test_rebel_search).
MUTATIONS = [
    ("infernal_machine/effects/outcomes.py", 'SearchLibrary(f"{m[1]} permanent|mv<={m[2].lower()}", "battlefield", False)',
     'SearchLibrary(f"{m[1]} permanent", "battlefield", False)', "only up to that mana value"),
    ("infernal_machine/effects/outcomes.py", 'SearchLibrary(f"{m[1]} permanent|mv<={m[2].lower()}", "battlefield", False)',
     'SearchLibrary(f"permanent|mv<={m[2].lower()}", "battlefield", False)', "only a Rebel"),
]


def activate(name, mana, x=None):
    """Seat 0, with `mana` lands, activates `name`'s search (X = `x`); its library holds Rebels of mana value 2, 3 and 4 and an Elf."""
    game, players = table3(lambda prompt, options: options.index(str(x)) if X_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    a.battlefield = lands(mana) + [Permanent(REAL[name], sick=False)]
    a.library = [ELF, REBEL_4, REBEL_3, REBEL_2]
    action = next(act for act in game.legal_actions(a) if act.startswith("Activate: " + name.split(",")[0]) and "Search" in act)
    game._perform(a, action)
    run_stack(game)
    offered = [options for prompt, options in players[0].prompts if SEARCH_CARD_PROMPT.matches(prompt)]
    return a, offered


def put(a):
    return sorted(p.card.name for p in a.battlefield if p.card.name.startswith(("Rebel", "Elf")))


class RebelSearchTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_only_a_rebel_up_to_that_mana_value(self):
        a, offered = activate("Ramosian Sergeant", 3)
        self.assertEqual((offered, put(a)), ([["Rebel Two"]], ["Rebel Two"]))

    def test_lin_sivvis_x_is_the_mana_value(self):
        a, offered = activate("Lin Sivvi, Defiant Hero", 3, x=3)
        self.assertEqual((offered, put(a)), ([["Rebel Three", "Rebel Two"]], ["Rebel Three"]))
        a, offered = activate("Lin Sivvi, Defiant Hero", 1, x=1)
        self.assertEqual((offered, put(a)), ([], []))


if __name__ == "__main__":
    unittest.main()
