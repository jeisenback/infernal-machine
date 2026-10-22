"""The effects of issue #72: populate after a token, copies of another creature or attacking, half a life total, doubling
counters on a target, a creature returning from its own death, putting or returning a creature card, and life lost."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.effects import (Amount, DefineX, CopyToken, CopyTokenAttacking, CreateTokens, DoubleCountersOnTarget, GainLife, Mill,
                                      Populate, PutFromHand, ReturnChosen, ReturnSelfToBattlefield, TargetLoseHalfLife,
                                      activated_abilities, spell_effects, triggered_abilities)
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, creature, lands, OGRE, pick, run_stack, table

SOLDIER = Card(name="Soldier", type_line="Token Creature — Soldier", colors=("W",), power="1", toughness="1")


def spell(text, kind="Sorcery", cost="{1}"):
    return Card(name="Spell", mana_cost=cost, type_line=kind, oracle_text=text)


def supported(test, card):
    test.assertEqual(unsupported_lines(card), [], card.oracle_text)


class PopulateAfterATokenTests(unittest.TestCase):
    TEXT = "Create a 3/3 green Beast creature token, then populate."

    def test_parse(self):
        effects = spell_effects(spell(self.TEXT))
        self.assertEqual((type(effects[0]), effects[1]), (CreateTokens, Populate()))
        supported(self, spell(self.TEXT))

    def test_the_new_token_can_be_the_one_copied(self):
        game, _, _ = table(pick(CAST, "Beast"))
        a = game.seats[0]
        a.hand, a.battlefield = [spell(self.TEXT)], lands(1) + [Permanent(SOLDIER)]
        game._priority_round(a)
        names = sorted(p.card.name for p in a.battlefield if "Token" in p.card.type_line)
        self.assertEqual(names, ["Beast", "Beast", "Soldier"])

    def test_with_no_other_token_it_copies_the_one_just_made(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [spell(self.TEXT)], lands(1)
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Token" in p.card.type_line), ["Beast", "Beast"])


class CopyAnotherTests(unittest.TestCase):
    CARD = creature("Mimic", 1, 1, "{T}: Create a token that's a copy of another target creature you control.")

    def test_parse(self):
        [ability] = activated_abilities(self.CARD)
        self.assertEqual(ability.effects, (CopyToken("creature you control", another=True),))
        supported(self, self.CARD)

    def test_it_cannot_copy_itself(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        mimic = Permanent(self.CARD)
        a.battlefield = [mimic]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)], [])  # nothing else to copy
        a.battlefield.append(Permanent(OGRE))
        self.assertTrue([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Mimic", "Ogre", "Ogre"])


class CopyAttackingTests(unittest.TestCase):
    CARD = creature("Army", 2, 2, "Whenever this creature attacks, create a token that's a copy of it, tapped and attacking.")

    def test_parse(self):
        [ability] = triggered_abilities(self.CARD)
        self.assertEqual((ability.event, ability.effects), ("attacks", (CopyTokenAttacking(),)))
        supported(self, self.CARD)

    def test_the_copy_attacks_the_same_player_without_attacking_again(self):
        def attack_all(prompt, options):
            return 1 if options[0] == "Don't attack" else 0

        game, _, _ = table(attack_all)
        a, b = game.seats
        army = Permanent(self.CARD)
        a.battlefield = [army]
        game.combat.declare_attackers(a)
        game._priority_round(a)
        [token] = [p for p in a.battlefield if "Token" in p.card.type_line]
        self.assertTrue(token.tapped)
        self.assertEqual([(x.attacker is army or x.attacker is token, x.defender) for x in game.combat.attacks],
                         [(True, b), (True, b)])
        self.assertEqual(len(game.pending), 0)  # the token was never declared as an attacker: no trigger of its own
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(b.life, 36)  # both hit


class HalfLifeTests(unittest.TestCase):
    def test_rounded_up_and_down(self):
        for word, expected in (("up", 20), ("down", 21)):
            card = spell(f"Target player loses half their life, rounded {word}.")
            self.assertEqual(spell_effects(card), [TargetLoseHalfLife("player", word == "up")])
            supported(self, card)
            game, _, _ = table(pick(CAST, "Player: B"))
            a, b = game.seats
            a.hand, a.battlefield = [card], lands(1)
            b.life = 41
            game._priority_round(a)
            self.assertEqual(b.life, expected, word)  # 41 loses 21 when rounded up (20 is left), 20 when rounded down

    def test_no_life_to_lose(self):
        game, _, _ = table()
        a, b = game.seats
        b.life = 0
        TargetLoseHalfLife("player", True).resolve(game, a, b)
        self.assertEqual(b.life, 0)


class DoubleCountersOnTargetTests(unittest.TestCase):
    def test_double_the_counters_on_a_target_creature(self):
        card = spell("Double the number of +1/+1 counters on target creature.")
        self.assertEqual(spell_effects(card), [DoubleCountersOnTarget("+1/+1", "creature")])
        supported(self, card)
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        marked, plain = Permanent(BEAR, counters={"+1/+1": 3}), Permanent(OGRE)
        a.hand, a.battlefield = [card], lands(1) + [marked, plain]
        game._priority_round(a)
        self.assertEqual((marked.counters, plain.counters), ({"+1/+1": 6}, {}))  # the Bear was the first target offered

    def test_a_creature_without_counters_gets_none(self):
        game, _, _ = table()
        plain = Permanent(OGRE)
        game.seats[0].battlefield = [plain]
        DoubleCountersOnTarget("+1/+1", "creature").resolve(game, game.seats[0], plain)
        self.assertEqual(plain.counters, {})


class ReturnSelfTests(unittest.TestCase):
    TAPPED = creature("Phoenix", 2, 2, "When this creature dies, return it to the battlefield tapped.")
    OWNER = creature("Ghoul", 2, 2, "When this creature dies, return it to the battlefield under its owner's control.")

    def test_parse(self):
        self.assertEqual(triggered_abilities(self.TAPPED)[0].effects, (ReturnSelfToBattlefield(tapped=True),))
        self.assertEqual(triggered_abilities(self.OWNER)[0].effects, (ReturnSelfToBattlefield(tapped=False),))
        supported(self, self.TAPPED)
        supported(self, self.OWNER)

    def test_it_comes_back_tapped(self):
        game, _, _ = table()
        a = game.seats[0]
        phoenix = Permanent(self.TAPPED)
        a.battlefield = [phoenix]
        game._leave_battlefield(phoenix, "dies")
        run_stack(game)
        [back] = a.battlefield
        self.assertEqual((back.card.name, back.tapped, back is phoenix), ("Phoenix", True, False))
        self.assertEqual(a.graveyard, [])

    def test_a_token_does_not_come_back(self):
        token = Card(name="Phoenix", type_line="Token Creature — Bird", power="2", toughness="2",
                     oracle_text="When this creature dies, return it to the battlefield tapped.")
        game, _, _ = table()
        a = game.seats[0]
        phoenix = Permanent(token)
        a.battlefield = [phoenix]
        game._leave_battlefield(phoenix, "dies")
        run_stack(game)
        self.assertEqual(a.battlefield, [])

    def test_under_its_owners_control_when_someone_else_had_it(self):
        game, _, _ = table()
        a, b = game.seats
        ghoul = Permanent(self.OWNER, owner=a)
        b.battlefield = [ghoul]  # a stolen creature
        game._leave_battlefield(ghoul, "dies")
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], b.battlefield), (["Ghoul"], []))

    def test_only_a_creature_that_died_can_do_it(self):
        card = creature("Odd", 1, 1, "When this creature enters, return it to the battlefield tapped.")
        self.assertEqual(triggered_abilities(card), ())  # "it" is not gone yet when it enters


class PutFromHandTests(unittest.TestCase):
    def test_you_may_put_a_creature_card_from_your_hand_onto_the_battlefield(self):
        card = spell("You may put a creature card from your hand onto the battlefield.")
        self.assertEqual(spell_effects(card), [PutFromHand("creature")])
        supported(self, card)
        game, _, _ = table(pick(CAST, "Ogre"))
        a = game.seats[0]
        a.hand, a.battlefield = [card, BEAR, OGRE], lands(1)
        game._priority_round(a)
        self.assertEqual(([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], a.hand), (["Ogre"], [BEAR]))

    def test_you_may_decline_and_with_no_creature_nothing_happens(self):
        game, _, _ = table(pick(CAST, "Don't"))
        a = game.seats[0]
        a.hand, a.battlefield = [spell("You may put a creature card from your hand onto the battlefield."), BEAR], lands(1)
        game._priority_round(a)
        self.assertEqual(a.hand, [BEAR])
        a.hand = [spell("You may put a creature card from your hand onto the battlefield.", cost="{0}")]
        PutFromHand("creature").resolve(game, a, None)  # no creature card in hand: it is a no-op, not an error


class MillThenReturnTests(unittest.TestCase):
    TEXT = "Mill three cards, then return a creature card from your graveyard to your hand."

    def test_parse(self):
        effects = spell_effects(spell(self.TEXT))
        self.assertEqual(effects, [Mill(3, "you"), ReturnChosen("creature", "hand")])
        supported(self, spell(self.TEXT))

    def test_it_can_return_the_card_it_milled_or_an_older_one(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        a = game.seats[0]
        a.library = [OGRE, Card(name="Rock", type_line="Artifact"), Card(name="Pebble", type_line="Artifact")] + a.library
        a.graveyard = [BEAR]
        a.hand, a.battlefield = [spell(self.TEXT)], lands(1)
        game._priority_round(a)
        self.assertEqual(([c.name for c in a.hand], sorted(c.name for c in a.graveyard)),
                         (["Ogre"], ["Bear", "Pebble", "Rock", "Spell"]))

    def test_no_creature_card_means_nothing_to_return(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.library = [Card(name="Rock", type_line="Artifact")] * 3 + a.library
        a.hand, a.battlefield = [spell(self.TEXT)], lands(1)
        game._priority_round(a)
        self.assertEqual(a.hand, [])


class LifeLostTests(unittest.TestCase):
    TEXT = "You gain life equal to the amount of life you lost this turn."

    def test_it_matches_what_you_lost_this_turn_only(self):
        supported(self, spell(self.TEXT))
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [spell(self.TEXT)], lands(1)
        game.change_life(a, -3)
        game.change_life(a, -4)
        game.change_life(a, 2)  # gaining life doesn't reduce what you lost
        game._priority_round(a)
        self.assertEqual(a.life, 40 - 3 - 4 + 2 + 7)

    def test_nothing_lost_gains_nothing_and_last_turn_does_not_count(self):
        game, _, _ = table()
        a = game.seats[0]
        for effect in (DefineX(Amount("life_lost")), GainLife("X")):  # "equal to the amount of life you lost this turn"
            effect.resolve(game, a, None)
        self.assertEqual(a.life, 40)
        game.change_life(a, -5)
        game.turn += 1
        for effect in (DefineX(Amount("life_lost")), GainLife("X")):
            effect.resolve(game, a, None)
        self.assertEqual(a.life, 35)
