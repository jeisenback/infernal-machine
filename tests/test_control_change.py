import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.combat import Attack
from infernal_machine.effects import GainControl, aura_controls, spell_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, OGRE
from tests.test_effects import FOREST, lands, pick, table

THREATEN = REAL["Threaten"]
MIND = Card(name="Mind Steal", mana_cost="{2}", type_line="Sorcery", oracle_text="Gain control of target creature.")
CONTROL_MAGIC = Card(name="Control Magic", mana_cost="{2}", type_line="Enchantment — Aura",
                     oracle_text="Enchant creature\nYou control enchanted creature.")


def setup(card, theirs=(OGRE,), policy=None):
    game, _, _ = table(policy or pick(CAST))
    a, b = game.seats
    a.hand = [card]
    a.battlefield = lands(4)
    b.battlefield = [Permanent(c) for c in theirs]
    return game, a, b


def creatures(seat):
    return sorted(p.card.name for p in seat.battlefield if "Creature" in p.card.type_line)


class ParseTests(unittest.TestCase):
    def test_threaten_is_one_effect(self):
        self.assertEqual(spell_effects(THREATEN), [GainControl("creature", True, True, True)])
        self.assertEqual(spell_effects(MIND), [GainControl("creature")])

    def test_untap_needs_something_to_refer_to(self):
        self.assertIsNone(spell_effects(Card(name="x", oracle_text="Untap that creature.")))
        self.assertIsNone(spell_effects(Card(name="x", oracle_text="You gain 1 life. Untap that creature.")))

    def test_control_magic(self):
        self.assertTrue(aura_controls(CONTROL_MAGIC))
        self.assertFalse(aura_controls(MIND))

    def test_the_report(self):
        for card in (THREATEN, MIND, CONTROL_MAGIC):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ThreatenTests(unittest.TestCase):
    def test_you_take_the_creature_untap_it_and_it_has_haste(self):
        game, a, b = setup(THREATEN)
        b.battlefield[0].tapped = True
        game._priority_round(a)
        ogre = next(p for p in a.battlefield if p.card.name == "Ogre")
        self.assertEqual((creatures(a), creatures(b)), (["Ogre"], []))
        self.assertFalse(ogre.tapped)
        self.assertTrue(game.has_keyword(ogre, "haste"))
        self.assertIs(ogre.owner, b)

    def test_it_can_attack_for_you(self):
        game, a, b = setup(THREATEN)
        game._priority_round(a)
        game.combat.declare_attackers.__self__  # the combat object exists
        a_policy = lambda prompt, options: 1 if options[0] == "Don't attack" else 0
        a.player.policy = a_policy
        game.combat.declare_attackers(a)
        self.assertEqual([x.attacker.card.name for x in game.combat.attacks], ["Ogre"])

    def test_it_goes_back_at_end_of_turn(self):
        game, a, b = setup(THREATEN)
        game._priority_round(a)
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual((creatures(a), creatures(b)), ([], ["Ogre"]))
        self.assertFalse(b.battlefield[0].control_eot)

    def test_a_permanent_steal_stays(self):
        game, a, b = setup(MIND)
        game._priority_round(a)
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual((creatures(a), creatures(b)), (["Ogre"], []))

    def test_it_is_summoning_sick_for_its_new_controller(self):
        game, a, b = setup(MIND)
        b.battlefield[0].sick = False
        game._priority_round(a)
        self.assertTrue(next(p for p in a.battlefield if p.card.name == "Ogre").sick)

    def test_it_dies_into_its_owners_graveyard(self):
        game, a, b = setup(MIND)
        game._priority_round(a)
        game.destroy(next(p for p in a.battlefield if p.card.name == "Ogre"))
        self.assertEqual(([c.name for c in a.graveyard], [c.name for c in b.graveyard]), (["Mind Steal"], ["Ogre"]))

    def test_it_leaves_combat(self):
        game, a, b = setup(MIND)
        ogre = b.battlefield[0]
        game.combat.attacks = [Attack(ogre, b, a)]
        game.gain_control(ogre, a)
        self.assertEqual(game.combat.attacks, [])

    def test_taking_what_you_already_control_only_untaps_it(self):
        game, a, _ = setup(THREATEN)
        mine = Permanent(BEAR, tapped=True)
        a.battlefield.append(mine)
        game.gain_control(mine, a, untap=True)
        self.assertFalse(mine.tapped)
        self.assertFalse(mine.sick)


class ControlMagicTests(unittest.TestCase):
    def cast(self):
        game, a, b = setup(CONTROL_MAGIC)
        game._priority_round(a)
        aura = next(p for p in a.battlefield if p.card.name == "Control Magic")
        return game, a, b, aura

    def test_you_control_the_enchanted_creature(self):
        game, a, b, aura = self.cast()
        self.assertEqual((creatures(a), creatures(b)), (["Ogre"], []))
        ogre = next(p for p in a.battlefield if p.card.name == "Ogre")
        self.assertIs(aura.attached_to, ogre)
        self.assertTrue(ogre.sick)

    def test_it_goes_back_when_the_aura_leaves(self):
        game, a, b, aura = self.cast()
        game.destroy(aura)
        game._check_state()
        self.assertEqual((creatures(a), creatures(b)), ([], ["Ogre"]))

    def test_the_aura_goes_to_its_owner_when_the_creature_dies(self):
        game, a, b, aura = self.cast()
        game.destroy(aura.attached_to)
        game._check_state()
        self.assertEqual(([c.name for c in a.graveyard], [c.name for c in b.graveyard]), (["Control Magic"], ["Ogre"]))

    def test_on_your_own_creature_it_changes_nothing(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear] + lands(2)
        a.hand = [CONTROL_MAGIC]
        game._priority_round(a)
        self.assertEqual(creatures(a), ["Bear"])
        self.assertFalse(bear.sick)

    def test_the_bot_aims_it_at_an_opponent(self):
        bot = BotPlayer("A", Deck([FOREST], [CONTROL_MAGIC], []))
        self.assertFalse(bot._is_buff_aura("Control Magic"))


if __name__ == "__main__":
    unittest.main()
