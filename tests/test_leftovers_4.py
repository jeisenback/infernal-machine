"""Leftover templates: delirium, "is equipped", "didn't cast a spell", multi-tribe lords, tapping a creature of a type as a cost,
"you attack with three or more creatures", "the end step", "When ... dies", and the Gift spells that change who loses what."""

import dataclasses
import unittest

from infernal_machine.effects import Condition, ReturnTransformed, activated_abilities, triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_activated import activation
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_gift import table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_transform import begin
from tests.test_x_targets import script

SURVIVALISTS = real("Backwoods Survivalists", "{3}{G}", "Creature — Human Warrior", "Delirium — This creature gets +1/+1 and has trample as long "
                    "as there are four or more card types among cards in your graveyard.", "4", "3")
ASSAILANT = real("Armed Assailant", "{2}{B}", "Creature — Human Villain", "Deathtouch\nAs long as this creature is equipped, it gets +2/+0 and has "
                 "menace.", "1", "3")
SWORD = real("Short Sword", "{1}", "Artifact — Equipment", "Equipped creature gets +1/+1.\nEquip {1}")
AMBUSHER = real("Nightpack Ambusher", "{2}{G}{G}", "Creature — Wolf", "Flash\nOther Wolves and Werewolves you control get +1/+1.\nAt the beginning of "
                "your end step, if you didn't cast a spell this turn, create a 2/2 green Wolf creature token.", "4", "4")
WOLF = real("Plain Wolf", "{1}{G}", "Creature — Wolf", "", "2", "2")
WEREWOLF = real("Plain Werewolf", "{1}{G}", "Creature — Werewolf", "", "2", "2")
VISIONARY = real("Raving Visionary", "{1}{U}", "Creature — Merfolk Wizard", "{U}, {T}: Draw a card, then discard a card.\nDelirium — {2}{U}, {T}: "
                 "Draw a card. Activate only if there are four or more card types among cards in your graveyard.", "1", "1")
MARKOV = real("Chosen of Markov", "{3}{B}", "Creature — Vampire", "{T}, Tap an untapped Vampire you control: Transform this creature.", "2", "2")
VAMPIRE = real("Plain Vampire", "{1}{B}", "Creature — Vampire", "", "2", "2")
LANDING = real("Landing Party", "{2}{W}", "Enchantment", "When you attack with three or more creatures, you gain 4 life.")
DRAGON = real("Archwing Dragon", "{2}{R}{R}", "Creature — Dragon", "Flying, haste\nAt the beginning of the end step, return this creature to its "
              "owner's hand.", "4", "4")
SENTRY = real("Desperate Sentry", "{2}{W}", "Creature — Human Soldier", "When this creature dies, create a 3/2 colorless Eldrazi Horror creature "
              "token.", "1", "2")
GREED = real("Consumed by Greed", "{1}{B}{B}", "Instant", "Gift a card\nTarget opponent sacrifices a creature with the greatest power among "
             "creatures they control. If the gift was promised, return target creature card from your graveyard to your hand.")
BLAST = real("Blooming Blast", "{1}{R}", "Instant", "Gift a Treasure\nBlooming Blast deals 2 damage to target creature. If the gift was promised, "
             "Blooming Blast also deals 3 damage to that creature's controller.")
RECYCLING = real("Peerless Recycling", "{1}{G}", "Instant", "Gift a card\nReturn target permanent card from your graveyard to your hand. If the gift "
                 "was promised, instead return two target permanent cards from your graveyard to your hand.")
CATHAR = dataclasses.replace(
    real("Loyal Cathar // Unhallowed Cathar", "{W}{W}", "Creature — Human Knight", "Vigilance\nWhen this creature dies, return it to the "
         "battlefield transformed under your control at the beginning of the next end step.", "2", "2"),
    flip=real("Unhallowed Cathar", "", "Creature — Zombie Knight", "Vigilance", "2", "1"))


def power(game, seat, card):
    return game.power(next(p for p in seat.battlefield if p.card is card))


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SURVIVALISTS, ASSAILANT, AMBUSHER, VISIONARY, MARKOV, LANDING, DRAGON, SENTRY, GREED, BLAST, RECYCLING, CATHAR):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_return_waits_for_the_end_step(self):
        [dies] = triggered_abilities(CATHAR)
        self.assertEqual(dies.effects, (ReturnTransformed(dies=True, end_step=True),))

    def test_the_tapped_creature_must_be_of_that_type(self):
        [ability] = activated_abilities(MARKOV)
        self.assertEqual((ability.tap_creatures, ability.tap_type), (1, "Vampire"))


class StaticTests(unittest.TestCase):
    def test_delirium_needs_four_card_types(self):
        game, a, b, c = table()
        a.battlefield = [Permanent(SURVIVALISTS)]
        self.assertEqual(power(game, a, SURVIVALISTS), 4)
        a.graveyard = [BEAR, OGRE, SWORD, SENTRY]  # creature x3, artifact: two types
        self.assertEqual(power(game, a, SURVIVALISTS), 4)
        a.graveyard = [BEAR, SWORD, GREED]  # creature, artifact, instant
        self.assertEqual(power(game, a, SURVIVALISTS), 4)
        a.graveyard = [BEAR, SWORD, GREED, LANDING]  # ... and an enchantment
        self.assertEqual(power(game, a, SURVIVALISTS), 5)

    def test_every_player_at_or_below_the_life_total(self):
        game, a, b, c = table()
        condition = Condition("each_life_at_most", 10)
        for life, holds in ((10, True), (11, False)):
            for seat in game.seats:
                seat.life = 10
            c.life = life
            self.assertEqual(game.condition_holds(condition, a, None), holds, life)

    def test_equipped_creature_gets_the_bonus(self):
        game, a, b, c = table()
        a.battlefield = [Permanent(ASSAILANT), Permanent(SWORD)]
        self.assertEqual(power(game, a, ASSAILANT), 1)
        a.battlefield[1].attached_to = a.battlefield[0]
        self.assertEqual(power(game, a, ASSAILANT), 4)  # +1 from the sword and +2 from being equipped

    def test_wolves_and_werewolves_but_nothing_else(self):
        game, a, b, c = table()
        a.battlefield = [Permanent(AMBUSHER), Permanent(WOLF), Permanent(WEREWOLF), Permanent(BEAR)]
        self.assertEqual([game.power(p) for p in a.battlefield], [4, 3, 3, 2])


class TriggerTests(unittest.TestCase):
    def test_a_wolf_token_when_no_spell_was_cast(self):
        game, a, b, c = table()
        game.turn = 1
        a.battlefield = [Permanent(AMBUSHER)]
        begin(game, "end", a)
        self.assertEqual(len(a.battlefield), 2)

    def test_no_token_after_casting_a_spell(self):
        game, a, b, c = table()
        game.turn = 1
        a.battlefield = [Permanent(AMBUSHER)]
        a.cast_log.append((game.turn, WOLF))
        begin(game, "end", a)
        self.assertEqual(len(a.battlefield), 1)

    def test_a_spell_cast_on_another_turn_does_not_count(self):
        game, a, b, c = table()
        game.turn = 1
        a.battlefield = [Permanent(AMBUSHER)]
        a.cast_log.append((game.turn - 1, WOLF))
        begin(game, "end", a)
        self.assertEqual(len(a.battlefield), 2)

    def test_the_end_step_of_any_player_returns_the_dragon(self):
        game, a, b, c = table()
        game.turn = 2
        a.battlefield = [Permanent(DRAGON)]
        begin(game, "end", b)
        self.assertEqual(a.battlefield, [])
        self.assertEqual(a.hand, [DRAGON])

    def test_when_a_creature_dies(self):
        game, a, b, c = table()
        a.battlefield = [Permanent(SENTRY)]
        game.destroy(a.battlefield[0])
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Eldrazi Horror"])

    def test_attacking_with_three_creatures(self):
        for count, life in ((2, 40), (3, 44)):
            game, _ = table3(attack_all)
            a = game.seats[0]
            a.hand = []
            a.battlefield = [Permanent(LANDING)] + [Permanent(BEAR, sick=False) for _ in range(count)]
            game.combat.declare_attackers(a)
            run_stack(game)
            self.assertEqual(a.life, life, count)

    def test_a_creature_returns_transformed_at_the_next_end_step(self):
        game, a, b, c = table()
        game.turn = 1
        a.battlefield = [Permanent(CATHAR)]
        game.destroy(a.battlefield[0])
        run_stack(game)
        self.assertEqual(a.battlefield, [])
        begin(game, "end", a)
        [back] = a.battlefield
        self.assertEqual(back.card.name, "Unhallowed Cathar")


class CostTests(unittest.TestCase):
    def test_delirium_unlocks_the_ability(self):
        game, a, b, c = table(mana=3)
        a.battlefield += [Permanent(VISIONARY, sick=False)]
        self.assertEqual(len(activation(game, a, "Draw a card.")), 0)
        a.graveyard = [BEAR, SWORD, GREED, LANDING]
        self.assertEqual(len(activation(game, a, "{2}{U}, {T}")), 1)

    def test_another_creature_of_the_type_has_to_be_tapped(self):
        game, a, b, c = table(mana=0)
        a.battlefield = [Permanent(MARKOV, sick=False), Permanent(BEAR, sick=False)]
        self.assertEqual(activation(game, a, "Transform"), [])
        a.battlefield.append(Permanent(VAMPIRE, sick=False))
        self.assertEqual(len(activation(game, a, "Transform")), 1)

    def test_the_vampire_is_the_one_tapped(self):
        game, a, b, c = table(mana=0)
        a.battlefield = [Permanent(MARKOV, sick=False), Permanent(BEAR, sick=False), Permanent(VAMPIRE, sick=False)]
        game._perform(a, activation(game, a, "Transform")[0])
        self.assertEqual([p.card.name for p in a.battlefield if p.tapped], ["Chosen of Markov", "Plain Vampire"])


class SpellTests(unittest.TestCase):
    def test_the_creature_with_the_greatest_power_is_sacrificed(self):
        game, a, b, c = table(GREED, mana=3, policy=script("Don't"))
        b.battlefield = [Permanent(BEAR), Permanent(OGRE)]
        game._perform(a, CAST + GREED.name)
        run_stack(game)
        self.assertEqual([p.card for p in b.battlefield], [BEAR])

    def test_the_gift_gets_a_creature_back(self):
        game, a, b, c = table(GREED, mana=3)
        a.graveyard = [OGRE]
        b.battlefield = [Permanent(BEAR)]
        game._perform(a, CAST + GREED.name)
        run_stack(game)
        self.assertEqual(a.hand, [OGRE])

    def test_the_controller_takes_damage_only_if_promised(self):
        for policy, life in ((script("Don't"), 40), (script("Give"), 37)):
            game, a, b, c = table(BLAST, mana=2, policy=policy)
            b.battlefield = [Permanent(OGRE)]
            game._perform(a, CAST + BLAST.name)
            run_stack(game)
            self.assertEqual(b.life, life)

    def test_two_cards_instead_of_one(self):
        game, a, b, c = table(RECYCLING, mana=2)
        a.graveyard = [BEAR, OGRE, SWORD]
        game._perform(a, CAST + RECYCLING.name)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)
        self.assertEqual(len(a.graveyard), 2)  # the one left and the spell itself


if __name__ == "__main__":
    unittest.main()
