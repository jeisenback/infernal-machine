import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Combat
from infernal_machine.effects import (PutAttackingFromHand, aura_kind, attached_abilities, reanimation_aura,
                                      triggered_abilities)
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.real import REAL

ANIMATE = REAL["Animate Dead"]
KAALIA = REAL["Kaalia of the Vast"]
OGRE = Card(name="Ogre", mana_cost="{3}", type_line="Creature — Ogre", power="4", toughness="4")
DRAGON = Card(name="Shivan Dragon", mana_cost="{4}{R}{R}", type_line="Creature — Dragon", power="5", toughness="5")
ANGEL = Card(name="Serra Angel", mana_cost="{3}{W}{W}", type_line="Creature — Angel", power="4", toughness="4")
BEAR = Card(name="Bear", mana_cost="{1}{G}", type_line="Creature — Bear", power="2", toughness="2")
DANCE_TEXT = ('When this Aura enters, if it\'s on the battlefield, it loses "enchant creature card in a graveyard" and gains '
              '"enchant creature put onto the battlefield with this Aura." Put enchanted creature card onto the battlefield '
              'tapped under your control and attach this Aura to it. When this Aura leaves the battlefield, that creature\'s '
              'controller sacrifices it.')


def resolve_everything(game):
    game._put_triggers_on_stack()
    while game.stack:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()
    game._check_state()


class AnimateDeadParseTests(unittest.TestCase):
    def test_the_real_text(self):
        self.assertEqual(reanimation_aura(ANIMATE), (False,))
        self.assertEqual(aura_kind(ANIMATE), "creature card in a graveyard")
        self.assertEqual(attached_abilities(ANIMATE)[0].modifier.power, -1)
        self.assertEqual(unsupported_lines(ANIMATE), [])

    def test_the_tapped_version(self):
        card = Card(name="Dance", mana_cost="{1}{B}", type_line="Enchantment — Aura",
                    oracle_text="Enchant creature card in a graveyard\n" + DANCE_TEXT)
        self.assertEqual(reanimation_aura(card), (True,))

    def test_other_cards_are_not_reanimation_auras(self):
        self.assertIsNone(reanimation_aura(REAL["Rancor"]))


class AnimateDeadTests(unittest.TestCase):
    def board(self, graveyard_of_b=(OGRE,)):
        game, _ = table3()
        a, b, _ = game.seats
        a.hand = [ANIMATE]
        a.battlefield = lands(2)
        b.graveyard = list(graveyard_of_b)
        return game, a, b

    def cast(self, game, a):
        game._perform(a, CAST + "Animate Dead")
        resolve_everything(game)

    def test_the_creature_comes_back_under_your_control_with_the_aura(self):
        game, a, b = self.board()
        self.cast(game, a)
        creature = next(p for p in a.battlefield if p.card is OGRE)
        aura = next(p for p in a.battlefield if p.card is ANIMATE)
        self.assertIs(aura.attached_to, creature)
        self.assertEqual(b.graveyard, [])
        self.assertEqual((game.power(creature), game.toughness(creature)), (3, 4))  # "-1/-0"
        self.assertEqual(creature.owner, b)  # it is still their card

    def test_it_is_only_castable_with_a_creature_card_in_a_graveyard(self):
        game, a, b = self.board(graveyard_of_b=())
        self.assertNotIn(CAST + "Animate Dead", game.legal_actions(a))
        b.graveyard = [OGRE]
        self.assertIn(CAST + "Animate Dead", game.legal_actions(a))
        b.graveyard = [Card(name="Bolt", mana_cost="{R}", type_line="Instant")]  # not a creature card
        self.assertNotIn(CAST + "Animate Dead", game.legal_actions(a))

    def test_if_the_card_is_gone_the_aura_fizzles(self):
        game, a, b = self.board()
        game._perform(a, CAST + "Animate Dead")
        b.graveyard = []  # exiled in response
        resolve_everything(game)
        self.assertEqual([c.name for c in a.graveyard], ["Animate Dead"])
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], [])

    def test_when_the_aura_leaves_the_creature_is_sacrificed(self):
        game, a, b = self.board()
        self.cast(game, a)
        aura = next(p for p in a.battlefield if p.card is ANIMATE)
        game._leave_battlefield(aura, "destroyed")
        game._check_state()
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], [])
        self.assertEqual([c.name for c in b.graveyard], ["Ogre"])  # back in its owner's graveyard

    def test_when_the_creature_dies_the_aura_goes_to_the_graveyard(self):
        game, a, b = self.board()
        self.cast(game, a)
        creature = next(p for p in a.battlefield if p.card is OGRE)
        game._leave_battlefield(creature, "dies")
        game._check_state()
        self.assertEqual([c.name for c in a.graveyard], ["Animate Dead"])


class KaaliaTests(unittest.TestCase):
    def attack(self, hand, choose=("Attack Player", "Yes", "Shivan", "Serra")):
        game, _ = table3(pick(*choose))
        a, b, _ = game.seats
        kaalia = Permanent(KAALIA)
        a.battlefield = [kaalia]
        a.hand = list(hand)
        game.combat = Combat(game)
        game.combat.declare_attackers(a)
        resolve_everything(game)
        return game, a, b, kaalia

    def test_the_real_text(self):
        [ability] = triggered_abilities(KAALIA)
        self.assertEqual((ability.event, ability.optional), ("attacks_player", True))
        self.assertEqual(ability.effects, (PutAttackingFromHand(("Angel", "Demon", "Dragon")),))
        self.assertEqual(unsupported_lines(KAALIA), [])

    def test_a_dragon_enters_tapped_and_attacking_the_same_opponent(self):
        game, a, b, kaalia = self.attack([DRAGON, BEAR])
        dragon = next(p for p in a.battlefield if p.card is DRAGON)
        self.assertTrue(dragon.tapped)
        attack = next(x for x in game.combat.attacks if x.attacker is dragon)
        self.assertIs(attack.defender, b)
        self.assertEqual([c.name for c in a.hand], ["Bear"])  # the Bear is not an Angel, Demon or Dragon

    def test_it_can_be_declined(self):
        game, a, b, kaalia = self.attack([DRAGON], choose=("Attack Player", "No"))
        self.assertEqual([p.card.name for p in a.battlefield], ["Kaalia of the Vast"])
        self.assertEqual([c.name for c in a.hand], ["Shivan Dragon"])

    def test_nothing_to_put_in(self):
        game, a, b, kaalia = self.attack([BEAR])
        self.assertEqual([p.card.name for p in a.battlefield], ["Kaalia of the Vast"])

    def test_several_choices_ask_which(self):
        game, a, b, kaalia = self.attack([DRAGON, ANGEL], choose=("Attack Player", "Yes", "Serra"))
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Kaalia of the Vast", "Serra Angel"])
        self.assertEqual([c.name for c in a.hand], ["Shivan Dragon"])

    def test_the_new_attacker_does_not_trigger_attack_abilities(self):
        game, a, b, kaalia = self.attack([DRAGON])
        self.assertEqual(sum(1 for p in a.battlefield if p.card is KAALIA), 1)
        self.assertEqual(len(game.combat.attacks), 2)  # Kaalia and the Dragon, no more


if __name__ == "__main__":
    unittest.main()
