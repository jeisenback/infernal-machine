"""Earthbend N: a land you control becomes a 0/0 creature with haste for good, with N +1/+1 counters, and returns tapped when it
dies or is exiled (Ba Sing Se, #564 row 10)."""

import unittest

from infernal_machine.characteristics import PLUS
from infernal_machine.effects import Earthbend, activated_abilities, spell_effects, triggered_abilities
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, activate, end_turn, lands, pick, real, run_stack, table3

BA_SING_SE = real("Ba Sing Se", "", "Land", "This land enters tapped unless you control a basic land.\n{T}: Add {G}.\n{2}{G}, {T}: Earthbend 2. "
                                            "Activate only as a sorcery. (Target land you control becomes a 0/0 creature with haste that's "
                                            "still a land. Put two +1/+1 counters on it. When it dies or is exiled, return it to the "
                                            "battlefield tapped.)")
LESSON = real("Earthbending Lesson", "{1}{G}", "Sorcery — Lesson", "Earthbend 4. (Target land you control becomes a 0/0 creature with haste "
                                                                   "that's still a land. Put four +1/+1 counters on it. When it dies or is "
                                                                   "exiled, return it to the battlefield tapped.)")
RUFFIANS = real("Earth Village Ruffians", "{2}{G}", "Creature — Human Warrior", "When this creature dies, earthbend 2.", "3", "2")


class ParseTests(unittest.TestCase):
    def test_the_cards_are_read(self):
        for card in (BA_SING_SE, LESSON, RUFFIANS):
            self.assertEqual(unsupported_lines(card), [], card.name)
        ability = activated_abilities(BA_SING_SE)[0]
        self.assertEqual((ability.mana_cost, ability.tap, ability.sorcery_speed, list(ability.effects)), ("{2}{G}", True, True, [Earthbend(2)]))
        self.assertEqual(spell_effects(LESSON), [Earthbend(4)])
        self.assertEqual(list(triggered_abilities(RUFFIANS)[0].effects), [Earthbend(2)])


class EarthbendTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(pick("Forest"))  # the Forest is the land earthbent
        self.a, self.b, _ = self.game.seats
        self.city = Permanent(BA_SING_SE)
        self.forest = Permanent(FOREST)
        self.a.battlefield = [self.city, self.forest] + lands(3)
        self.b.battlefield = [Permanent(FOREST)]

    def bend(self):
        activate(self.game, self.a, "Earthbend 2")

    def test_the_land_becomes_a_hasty_creature_with_the_counters_and_stays_a_land(self):
        self.bend()
        self.assertTrue(self.city.tapped)
        self.assertEqual(self.forest.card.type_line, "Basic Land Creature — Forest")
        self.assertEqual((self.game.power(self.forest), self.game.toughness(self.forest)), (2, 2))
        self.assertEqual(self.forest.counters.get(PLUS), 2)
        self.assertTrue(self.game.has_keyword(self.forest, "haste"))
        self.forest.tapped = False  # it helped pay for the ability
        self.assertTrue(any(s.permanent is self.forest for s in self.game._mana_sources(self.a)))  # still a land

    def test_the_animation_outlasts_the_turn(self):
        self.bend()
        end_turn(self.game, self.a)
        self.assertIn("Creature", self.forest.card.type_line)
        self.assertEqual(self.game.power(self.forest), 2)

    def test_only_as_a_sorcery(self):
        self.game.active = 1
        self.assertFalse(any(a.startswith(ACTIVATE) and "Earthbend" in a for a in self.game.legal_actions(self.a)))

    def test_an_opponents_land_is_not_a_target(self):
        options = [p for _, p in self.game.target_options("land you control", self.a)]
        self.assertNotIn(self.b.battlefield[0], options)
        self.assertIn(self.forest, options)

    def test_when_it_dies_it_returns_tapped_as_a_plain_land(self):
        self.bend()
        self.game.remove_counters(self.forest, PLUS, 2)
        self.game._check_state()  # a 0/0 dies
        self.assertNotIn(self.forest, self.a.battlefield)
        run_stack(self.game)
        back = next(p for p in self.a.battlefield if p.card is FOREST)
        self.assertTrue(back.tapped)
        self.assertNotIn("Creature", back.card.type_line)
        self.assertEqual(back.counters, {})
        self.assertNotIn(FOREST, self.a.graveyard)

    def test_when_it_is_exiled_it_returns_tapped(self):
        self.bend()
        self.game._leave_together([(self.forest, "exiled")], "exile")
        self.assertIn(FOREST, self.a.exile)
        run_stack(self.game)
        back = next(p for p in self.a.battlefield if p.card is FOREST)
        self.assertTrue(back.tapped)
        self.assertNotIn("Creature", back.card.type_line)
        self.assertNotIn(FOREST, self.a.exile)

    def test_an_unbent_land_that_leaves_stays_gone(self):
        self.game._leave_together([(self.forest, "exiled")], "exile")
        run_stack(self.game)
        self.assertIn(FOREST, self.a.exile)
        self.assertFalse(any(p.card is FOREST for p in self.a.battlefield))


if __name__ == "__main__":
    unittest.main()
