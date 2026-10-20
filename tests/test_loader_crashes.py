"""Two cards the coverage audit found crashing the report instead of being understood or reported: Raise the Past (a plural
"cards with mana value N or less" lost its last letter) and Zaxara, the Exemplary ("put X +1/+1 counters" arrived lowercased)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.common import _count
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, Table

RAISE = real("Raise the Past", "{2}{W}{W}", "Sorcery",
             "Return all creature cards with mana value 2 or less from your graveyard to the battlefield.", colors=("W",))
ZAXARA = Card(name="Zaxara, the Exemplary", mana_cost="{1}{B}{G}{U}", cmc=4.0, type_line="Legendary Creature — Nightmare Hydra",
              power="3", toughness="3", oracle_text="Deathtouch\n{T}: Add two mana of any one color.\nWhenever you cast a spell with {X} in its "
                                                    "mana cost, create a 0/0 green Hydra creature token, then put X +1/+1 counters on it.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ONE = real("One Drop", "{1}", "Creature — Human", "", "1", "1")
TWO = real("Two Drop", "{1}{1}", "Creature — Human", "", "2", "2")
THREE = real("Three Drop", "{3}", "Creature — Human", "", "3", "3")
CHEAP_SPELL = real("Cheap Spell", "{1}", "Instant", "Draw a card.")


class RaiseThePastTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(RAISE), [])

    def test_creature_cards_of_mana_value_two_or_less_return_and_nothing_else(self):
        t = Table(RAISE, graveyard=[ONE, TWO, THREE, CHEAP_SPELL]).cast()
        self.assertEqual(sorted(p.card.name for p in t.a.battlefield if p.card.type_line.startswith("Creature")), ["One Drop", "Two Drop"])
        self.assertEqual(sorted(c.name for c in t.a.graveyard), ["Cheap Spell", "Raise the Past", "Three Drop"])

    def test_an_opponents_graveyard_is_left_alone(self):
        t = Table(RAISE, graveyard=[ONE])
        t.b.graveyard = [TWO]
        t.cast()
        self.assertEqual([c.name for c in t.b.graveyard], ["Two Drop"])


class ZaxaraTests(unittest.TestCase):
    X_SPELL = real("X Draw", "{X}{R}", "Sorcery", "Draw a card.", colors=("R",))
    PLAIN = real("Plain Draw", "{R}", "Sorcery", "Draw a card.", colors=("R",))

    def hydras(self, t):
        return [dict(p.counters) for p in t.a.battlefield if p.card.name == "Hydra"]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(ZAXARA), [])

    def test_casting_a_spell_with_x_makes_a_hydra_with_x_counters(self):
        t = Table(self.X_SPELL, "3", n=0, mine=[Permanent(ZAXARA)] + [Permanent(MOUNTAIN) for _ in range(5)]).cast()
        self.assertEqual(self.hydras(t), [{"+1/+1": 3}])

    def test_a_spell_without_x_makes_nothing(self):
        t = Table(self.PLAIN, n=0, mine=[Permanent(ZAXARA), Permanent(MOUNTAIN)]).cast()
        self.assertEqual(self.hydras(t), [])

    def test_x_of_zero_leaves_no_hydra_behind(self):
        t = Table(self.X_SPELL, "0", n=0, mine=[Permanent(ZAXARA), Permanent(MOUNTAIN)]).cast()
        self.assertEqual(self.hydras(t), [], "a 0/0 token dies at once")


class CountTests(unittest.TestCase):
    def test_x_in_any_case(self):
        for word in ("X", "x"):
            self.assertEqual(_count(word), "X")
        self.assertEqual((_count("twice X"), _count("twice x")), ("2X", "2X"))
        self.assertEqual((_count("half X"), _count("half x down"), _count("half X up")), ("hX", "hX", "hX+"))

    def test_numbers_and_words(self):
        self.assertEqual((_count("3"), _count("three"), _count("Three")), (3, 3, 3))


if __name__ == "__main__":
    unittest.main()
