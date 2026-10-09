"""Infinite Coursework, the last card of issue #85: "When this Aura enters, tap enchanted creature. It becomes unprepared."
and "Enchanted creature loses all abilities and doesn't untap during its controller's untap step." Its text is from Scryfall.
Each effect has a control case without the Aura.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, BIRD, creature
from tests.test_effects import FOREST
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire, prepper

COURSEWORK = Card(name="Infinite Coursework", mana_cost="{2}{U}", type_line="Enchantment — Aura",
                  oracle_text="Enchant creature\nWhen this Aura enters, tap enchanted creature. It becomes unprepared.\n"
                              "Enchanted creature loses all abilities and doesn't untap during its controller's untap step.")
HASTE_AURA = Card(name="Spurs", type_line="Enchantment — Aura", oracle_text="Enchant creature\nEnchanted creature has haste.")
GREEN = Card(name="Green", mana_cost="{G}", cmc=1.0, type_line="Sorcery", oracle_text="Draw a card.")


def board(victim_card, aura=True):
    game, _ = table3()
    a, b, _ = game.seats
    victim = Permanent(victim_card)
    a.battlefield = [victim]
    coursework = Permanent(COURSEWORK, attached_to=victim) if aura else None
    if aura:
        a.battlefield.append(coursework)
    return game, a, victim, coursework


class ParseTests(unittest.TestCase):
    def test_every_line_is_supported(self):
        self.assertEqual(unsupported_lines(COURSEWORK), [])

    def test_a_plain_tap_line_is_supported_too(self):
        card = Card(name="Frozen", type_line="Enchantment — Aura", oracle_text="Enchant creature\n"
                    "When this Aura enters, tap enchanted creature.")
        self.assertEqual(unsupported_lines(card), [])


class EntersTests(unittest.TestCase):
    def test_it_taps_the_enchanted_creature_and_unprepares_it(self):
        game, a, victim, aura = board(prepper("", "Student"))
        victim.prepared = True
        fire(game, a, aura, "enters")
        self.assertEqual((victim.tapped, victim.prepared), (True, False))

    def test_an_unprepared_creature_is_just_tapped(self):
        game, a, victim, aura = board(BEAR)
        fire(game, a, aura, "enters")
        self.assertEqual((victim.tapped, victim.prepared), (True, False))

    def test_only_the_enchanted_creature_is_affected(self):
        game, a, victim, aura = board(BEAR)
        other = Permanent(prepper("", "Other"), prepared=True)
        a.battlefield.append(other)
        fire(game, a, aura, "enters")
        self.assertEqual((other.tapped, other.prepared), (False, True))

    def test_nothing_happens_if_it_is_not_attached(self):
        game, a, victim, aura = board(BEAR)
        aura.attached_to = None
        fire(game, a, aura, "enters")
        self.assertFalse(victim.tapped)


class DoesNotUntapTests(unittest.TestCase):
    def untap(self, aura):
        game, a, victim, coursework = board(BEAR, aura=aura)
        other = Permanent(BEAR, tapped=True)
        a.battlefield.append(other)
        victim.tapped = True
        game.active, game.step = 0, "untap"
        game._turn_based_actions(a)
        return victim, other

    def test_it_stays_tapped_while_the_other_creatures_untap(self):
        victim, other = self.untap(aura=True)
        self.assertEqual((victim.tapped, other.tapped), (True, False))

    def test_without_the_aura_it_untaps(self):
        victim, other = self.untap(aura=False)
        self.assertEqual((victim.tapped, other.tapped), (False, False))

    def test_it_untaps_once_the_aura_is_gone(self):
        game, a, victim, coursework = board(BEAR)
        victim.tapped = True
        a.battlefield.remove(coursework)
        game.active, game.step = 0, "untap"
        game._turn_based_actions(a)
        self.assertFalse(victim.tapped)


class LosesAllAbilitiesTests(unittest.TestCase):
    def test_keywords_are_lost(self):
        game, a, victim, _ = board(BIRD)
        self.assertFalse(game.has_keyword(victim, "flying"))

    def test_keywords_stay_without_the_aura(self):
        game, a, victim, _ = board(BIRD, aura=False)
        self.assertTrue(game.has_keyword(victim, "flying"))

    def test_the_size_is_not_an_ability(self):
        game, a, victim, _ = board(BEAR)
        self.assertEqual((game.power(victim), game.toughness(victim)), (2, 2))

    def test_a_keyword_another_aura_grants_still_works(self):
        game, a, victim, _ = board(BIRD)
        a.battlefield.append(Permanent(HASTE_AURA, attached_to=victim))
        self.assertEqual((game.has_keyword(victim, "flying"), game.has_keyword(victim, "haste")), (False, True))

    def test_its_own_triggers_stop(self):
        for aura, draws in ((True, 0), (False, 1)):
            game, a, victim, _ = board(creature("Scholar", 1, 1, "Whenever this creature attacks, draw a card."), aura=aura)
            a.library = [BEAR] * 3
            fire(game, a, victim, "attacks")
            self.assertEqual(len(a.hand), draws, f"aura={aura}")

    def test_its_watching_triggers_stop(self):
        for aura, draws in ((True, 0), (False, 1)):
            game, a, victim, _ = board(creature("Mourner", 1, 1, "Whenever another creature you control dies, draw a card."),
                                       aura=aura)
            doomed = Permanent(BEAR)
            a.battlefield.append(doomed)
            a.library = [BEAR] * 3
            game._leave_together([(doomed, "destroyed")])
            run_stack(game)
            self.assertEqual(len(a.hand), draws, f"aura={aura}")

    def test_its_activated_abilities_are_not_offered(self):
        for aura, offered in ((True, False), (False, True)):
            game, a, victim, _ = board(creature("Tapper", 1, 1, "{T}: Draw a card."), aura=aura)
            victim.sick = False
            game.active, game.step = 0, "main1"
            actions = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE)]
            self.assertEqual(bool(actions), offered, f"aura={aura}")

    def test_its_mana_ability_stops(self):
        for aura, payable in ((True, False), (False, True)):
            game, a, victim, _ = board(creature("Elf", 1, 1, "{T}: Add {G}."), aura=aura)
            victim.sick = False
            self.assertEqual(game._payment(a, GREEN) is not None, payable, f"aura={aura}")

    def test_its_filter_mana_ability_stops(self):
        blue_white = Card(name="Blue White", mana_cost="{W}{U}", cmc=2.0, type_line="Sorcery", oracle_text="Draw a card.")
        for aura, payable in ((True, False), (False, True)):
            game, a, victim, _ = board(creature("Filter", 1, 1, "{1}, {T}: Add {W}{U}."), aura=aura)
            victim.sick = False
            a.battlefield.append(Permanent(FOREST))
            self.assertEqual(game._payment(a, blue_white) is not None, payable, f"aura={aura}")

    def test_a_land_with_the_aura_cannot_tap_for_mana(self):
        game, a, land, _ = board(Card(name="Treefolk Land", type_line="Land Creature — Forest", power="2", toughness="2",
                                      produced_mana=("G",)))
        self.assertIsNone(game._payment(a, GREEN))

    def test_its_static_abilities_stop(self):
        for aura, bonus in ((True, 0), (False, 1)):
            game, a, victim, _ = board(creature("Lord", 1, 1, "Other creatures you control get +1/+1."), aura=aura)
            other = Permanent(BEAR)
            a.battlefield.append(other)
            self.assertEqual(game.power(other), 2 + bonus, f"aura={aura}")


if __name__ == "__main__":
    unittest.main()
