"""Aura grants and other static buffs from the real cards in issue #75."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import attached_abilities
from infernal_machine.game import CHOOSE_TYPE_PROMPT, SACRIFICE_COST_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

RELIC = Card(name="Relic", type_line="Artifact")


class EldraziConscriptionTests(unittest.TestCase):
    def test_it_is_understood(self):
        card = REAL["Eldrazi Conscription"]
        self.assertEqual(unsupported_lines(card), [])
        [buff] = attached_abilities(card)
        self.assertEqual((buff.modifier.power, buff.modifier.keywords), (10, frozenset({"trample", "annihilator 2"})))

    def test_the_enchanted_creature_has_annihilator_2(self):
        game, _ = table3(pick("Attack Player: B"))
        a, b, _c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(REAL["Eldrazi Conscription"], attached_to=bear)]
        b.battlefield = [Permanent(RELIC) for _ in range(5)]
        self.assertEqual((game.power(bear), game.annihilator(bear)), (12, 2))
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 3)  # two sacrificed

    def test_no_annihilator_without_the_aura(self):
        game, _ = table3(pick("Attack Player: B"))
        a, b, _c = game.seats
        a.battlefield = [Permanent(BEAR)]
        b.battlefield = [Permanent(RELIC)]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 1)


class AngelicDestinyTests(unittest.TestCase):
    def test_it_pumps_gives_keywords_and_makes_the_creature_an_angel(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        lord = Card(name="Angel Lord", type_line="Creature " + chr(0x2014) + " Angel", power="1", toughness="1",
                    oracle_text="Angels you control get +1/+1.")
        a.battlefield = [bear, Permanent(lord)]
        self.assertEqual(game.power(bear), 2)
        a.battlefield.append(Permanent(REAL["Angelic Destiny"], attached_to=bear))
        self.assertEqual((game.power(bear), game.toughness(bear)), (2 + 4 + 1, 2 + 4 + 1))  # +4/+4, and the Angel lord's +1/+1
        self.assertEqual((game.has_keyword(bear, "flying"), game.has_keyword(bear, "first strike")), (True, True))
        self.assertIn("Angel", game.subtypes(bear))
        self.assertEqual(game.power(a.battlefield[1]), 1 + 1)  # the lord itself is an Angel too


class FallenIdealTests(unittest.TestCase):
    def test_flying_a_sacrifice_ability_and_it_returns_to_hand(self):
        def policy(prompt, options):  # sacrifice the last creature listed, the spare Bear
            return len(options) - 1 if prompt.startswith(SACRIFICE_COST_PROMPT) else pick("Activate")(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        bear, fodder = Permanent(BEAR), Permanent(BEAR)
        ideal = Permanent(REAL["Fallen Ideal"], attached_to=bear)
        a.battlefield = [bear, fodder, ideal]
        self.assertTrue(game.has_keyword(bear, "flying"))
        [action] = [x for x in game._activations(a, True) if "Sacrifice a creature" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((game.power(bear), game.toughness(bear)), (2 + 2, 2 + 1))
        self.assertEqual(len(a.battlefield) - 1, 1)  # one Bear was the cost
        game._leave_battlefield(ideal, "destroyed")
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Fallen Ideal"])


class PatchworkBannerTests(unittest.TestCase):
    def test_it_names_the_most_common_type_and_pumps_it(self):
        game, _ = table3()
        a = game.seats[0]
        wolf = Card(name="Wolf", type_line="Creature " + chr(0x2014) + " Wolf", power="2", toughness="2")
        bear = Card(name="Bear", type_line="Creature " + chr(0x2014) + " Bear", power="2", toughness="2")
        a.library = [wolf, wolf, wolf, bear]
        a.battlefield = [Permanent(wolf), Permanent(bear)]
        banner = Permanent(REAL["Patchwork Banner"])
        game._enter(a, banner)
        self.assertEqual(banner.chosen_type, "Wolf")
        self.assertEqual((game.power(a.battlefield[0]), game.power(a.battlefield[1])), (3, 2))

    def test_the_player_chooses(self):
        game, players = table3(lambda prompt, options: options.index("Bear") if prompt.startswith(CHOOSE_TYPE_PROMPT) else 0)
        a = game.seats[0]
        wolf = Card(name="Wolf", type_line="Creature " + chr(0x2014) + " Wolf", power="2", toughness="2")
        bear = Card(name="Bear", type_line="Creature " + chr(0x2014) + " Bear", power="2", toughness="2")
        a.library = [wolf, bear]
        a.battlefield = [Permanent(bear)]
        game._enter(a, Permanent(REAL["Patchwork Banner"]))
        self.assertEqual(game.power(a.battlefield[0]), 3)
