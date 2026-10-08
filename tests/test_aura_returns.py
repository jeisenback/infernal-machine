import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import ReturnAuraToBattlefield, ReturnDeadToBattlefield, ReturnSelfToHand, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

ANGELIC_DESTINY = Card(name="Angelic Destiny", mana_cost="{2}{W}{W}", type_line="Enchantment — Aura",
                       oracle_text="Enchant creature\nEnchanted creature gets +4/+4, has flying and first strike, and is "
                                   "an Angel in addition to its other types.\nWhen enchanted creature dies, return this "
                                   "card to its owner's hand.")
CHANGING_LOYALTY = REAL["Changing Loyalty"]
GHOULISH_IMPETUS = REAL["Ghoulish Impetus"]
GIFT = Card(name="Gift of Immortality", mana_cost="{2}{W}", type_line="Enchantment — Aura",
            oracle_text="Enchant creature\nWhen enchanted creature dies, return that card to the battlefield under its "
                        "owner's control. Return this card to the battlefield attached to that creature at the beginning "
                        "of the next end step.")
SCREAMS = Card(name="Screams from Within", mana_cost="{1}{B}{B}", type_line="Enchantment — Aura",
               oracle_text="Enchant creature\nEnchanted creature gets -1/-1.\nWhen enchanted creature dies, return this "
                           "card from your graveyard to the battlefield.")


def effects_of(card):
    [ability] = [a for a in triggered_abilities(card) if a.event == "host_dies"]
    return ability.effects


def kill(game, host):
    game._leave_battlefield(host, "dies")
    game._check_state()  # the Aura is no longer attached to anything
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_each_line_is_understood(self):
        self.assertEqual(effects_of(ANGELIC_DESTINY), (ReturnSelfToHand(),))
        self.assertEqual(effects_of(CHANGING_LOYALTY), (ReturnDeadToBattlefield(under_owner=False),))
        self.assertEqual(effects_of(GHOULISH_IMPETUS), (ReturnAuraToBattlefield("end_step"),))
        self.assertEqual(effects_of(GIFT), (ReturnDeadToBattlefield(under_owner=True),
                                            ReturnAuraToBattlefield("end_step", to_host=True)))
        self.assertEqual(effects_of(SCREAMS), (ReturnAuraToBattlefield("now"),))

    def test_the_report_no_longer_lists_these_lines(self):
        for card in (CHANGING_LOYALTY, GHOULISH_IMPETUS, GIFT, SCREAMS):
            self.assertFalse([l for l in unsupported_lines(card) if l.startswith("When enchanted")], card.name)
        self.assertFalse([l for l in unsupported_lines(ANGELIC_DESTINY) if l.startswith("When enchanted")])


class ReturnTests(unittest.TestCase):
    def test_angelic_destiny_returns_to_hand(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(ANGELIC_DESTINY, attached_to=bear)]
        kill(game, bear)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Angelic Destiny"], ["Bear"]))

    def test_changing_loyalty_steals_the_creature_back_under_your_control(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR, owner=b)
        a.battlefield = [Permanent(CHANGING_LOYALTY, attached_to=bear)]
        b.battlefield = [bear]
        kill(game, bear)
        self.assertEqual([p.card.name for p in a.battlefield], ["Bear"])
        self.assertEqual((b.battlefield, b.graveyard), ([], []))

    def test_screams_from_within_comes_back_on_a_creature(self):
        game, _ = table3()
        a = game.seats[0]
        bear, other = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [bear, other, Permanent(SCREAMS, attached_to=bear)]
        kill(game, bear)
        aura = next(p for p in a.battlefield if p.card is SCREAMS)
        self.assertIs(aura.attached_to, other)
        self.assertNotIn(SCREAMS, a.graveyard)

    def test_screams_stays_in_the_graveyard_with_nothing_to_enchant(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(SCREAMS, attached_to=bear)]
        kill(game, bear)
        self.assertIn(SCREAMS, a.graveyard)

    def test_ghoulish_impetus_waits_for_the_end_step(self):
        game, _ = table3()
        a = game.seats[0]
        game.step = "main1"
        bear, other = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [bear, other, Permanent(GHOULISH_IMPETUS, attached_to=bear)]
        kill(game, bear)
        self.assertIn(GHOULISH_IMPETUS, a.graveyard)
        [(turn, bring_back)] = game.at_end_step
        bring_back()
        self.assertEqual([p.card.name for p in a.battlefield], ["Bear", "Ghoulish Impetus"])
        self.assertNotIn(GHOULISH_IMPETUS, a.graveyard)

    def test_gift_of_immortality_returns_both_attached(self):
        game, _ = table3()
        a = game.seats[0]
        game.step = "main1"
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(GIFT, attached_to=bear)]
        kill(game, bear)
        self.assertEqual([p.card.name for p in a.battlefield], ["Bear"])  # the creature is back, the Aura waits
        [(turn, bring_back)] = game.at_end_step
        bring_back()
        creature, aura = a.battlefield
        self.assertIs(aura.attached_to, creature)
        self.assertEqual(a.graveyard, [])

    def test_gift_does_nothing_for_the_aura_if_the_creature_left_again(self):
        game, _ = table3()
        a = game.seats[0]
        game.step = "main1"
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(GIFT, attached_to=bear)]
        kill(game, bear)
        game._leave_battlefield(a.battlefield[0], "dies")
        [(turn, bring_back)] = game.at_end_step
        bring_back()
        self.assertEqual(a.battlefield, [])
        self.assertIn(GIFT, a.graveyard)


if __name__ == "__main__":
    unittest.main()
