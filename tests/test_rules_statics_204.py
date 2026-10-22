"""Rules-changing statics (#204): can't be countered, as though it had flash, who can cast or activate and when, and lands that are
also a basic land type; each from the card's own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Counter
from infernal_machine.game import CAST, ACTIVATE, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, pick, table3

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
URBORG = Card(name="Urborg, Tomb of Yawgmoth", type_line="Legendary Land", oracle_text="Each land is a Swamp in addition to its other land types.")
YAVIMAYA = Card(name="Yavimaya, Cradle of Growth", type_line="Legendary Land", oracle_text="Each land is a Forest in addition to its other land types.")
DRYAD = Card(name="Dryad of the Ilysian Grove", mana_cost="{2}{G}", cmc=3, type_line="Enchantment Creature — Nymph Dryad", power="2",
             toughness="4", oracle_text="You may play an additional land on each of your turns.\nLands you control are every basic land type in addition to their other types.")
RHYTHM = Card(name="Rhythm of the Wild", mana_cost="{1}{R}{G}", cmc=3, type_line="Enchantment",
              oracle_text="Creature spells you control can't be countered.")
SQUELCHER = Card(name="Chimil, the Inner Sun", mana_cost="{6}", cmc=6, type_line="Legendary Artifact", oracle_text="Spells you control can't be countered.")
LEYLINE = Card(name="Leyline of Anticipation", mana_cost="{2}{U}{U}", cmc=4, type_line="Enchantment",
               oracle_text="You may cast spells as though they had flash.")
VIVIEN = Card(name="Raff", type_line="Enchantment", oracle_text="You may cast creature spells as though they had flash.")
SPIRITS = Card(name="Rattlechains", type_line="Creature — Spirit", power="1", toughness="1",
               oracle_text="You may cast Spirit spells as though they had flash.")
WIZARDS = Card(name="Wizards of Thay", type_line="Creature — Human Wizard", power="1", toughness="1",
               oracle_text="You may cast sorcery spells as though they had flash.")
KUTZIL = Card(name="Voice of Victory", type_line="Creature — Human Bard", power="1", toughness="3", oracle_text="Your opponents can't cast spells during your turn.")
MARISI = Card(name="Marisi", type_line="Legendary Creature — Human Warrior", power="2", toughness="2", oracle_text="Your opponents can't cast spells during combat.")
RULE_OF_LAW = Card(name="Rule of Law", mana_cost="{2}{W}", cmc=3, type_line="Enchantment", oracle_text="Each player can't cast more than one spell each turn.")
DEADLOCK = Card(name="Moderation", mana_cost="{2}{W}", cmc=3, type_line="Enchantment", oracle_text="You can't cast more than one spell each turn.")
GOLEM = Card(name="Steel Golem", mana_cost="{3}", cmc=3, type_line="Artifact Creature — Golem", power="3", toughness="4", oracle_text="You can't cast creature spells.")
NIKYA = Card(name="Nullhide Ferox", type_line="Creature — Hydra", power="4", toughness="4", oracle_text="You can't cast noncreature spells.")
ABOLISHER = Card(name="Grand Abolisher", mana_cost="{W}{W}", cmc=2, type_line="Creature — Human Cleric", power="2", toughness="2",
                 oracle_text="During your turn, your opponents can't cast spells or activate abilities of artifacts, creatures, or enchantments.")
STONY = Card(name="Stony Silence", mana_cost="{1}{W}", cmc=2, type_line="Enchantment", oracle_text="Activated abilities of artifacts can't be activated.")
SOL_RING = Card(name="Sol Ring", mana_cost="{1}", cmc=1, type_line="Artifact", oracle_text="{T}: Add {C}{C}.")
LOOTER = Card(name="Looter", type_line="Artifact", oracle_text="{T}: You gain 1 life.")
ELF = Card(name="Llanowar Elves", mana_cost="{G}", cmc=1, type_line="Creature — Elf Druid", power="1", toughness="1", oracle_text="{T}: Add {G}.")
BEAR = Card(name="Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
SPIRIT = Card(name="Ghost", mana_cost="{U}", cmc=1, type_line="Creature — Spirit", power="1", toughness="1")
BOLT = Card(name="Shock", mana_cost="{R}", cmc=1, type_line="Instant", oracle_text="Shock deals 2 damage to any target.")
DIVINATION = Card(name="Divination", mana_cost="{2}{U}", cmc=3, type_line="Sorcery", oracle_text="Draw two cards.")
CHARM = Card(name="Mana Tithe", mana_cost="{G}", cmc=1, type_line="Instant", oracle_text="Draw a card.")
LAND_B = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
DARK = Card(name="Dark Ritual Spell", mana_cost="{B}", cmc=1, type_line="Instant", oracle_text="Draw a card.")


def world(mine=(), theirs=(), hand=(), active=0, policy=None, step="main1", lands_mine=0):
    game, _ = table3(policy) if policy else table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(c) for c in mine] + lands(lands_mine, FOREST)
    b.battlefield = [Permanent(c) for c in theirs]
    a.hand = list(hand)
    game.active, game.step = active, step
    return game, a, b


def castable(game, seat, card):
    return CAST + card.name in game.legal_actions(seat)


class CantBecounteredTests(unittest.TestCase):
    def counter(self, mine, card, theirs=()):
        game, a, b = world(mine, theirs)
        item = StackItem(card, a, [], [])
        game.stack.append(item)
        Counter().resolve(game, b, item)
        return item in game.stack

    def test_creature_spells_you_control(self):
        self.assertTrue(self.counter([RHYTHM], BEAR))
        self.assertFalse(self.counter([RHYTHM], DIVINATION))  # only creature spells
        self.assertFalse(self.counter([], BEAR))

    def test_all_your_spells(self):
        self.assertTrue(self.counter([SQUELCHER], DIVINATION))
        self.assertTrue(self.counter([SQUELCHER], BEAR))

    def test_an_opponents_does_not_protect_your_spell(self):
        self.assertFalse(self.counter([], BEAR, theirs=[RHYTHM]))


class FlashTests(unittest.TestCase):
    def test_any_spell_at_instant_speed(self):
        game, a, b = world([LEYLINE], hand=[BEAR], active=1)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST)]
        self.assertTrue(castable(game, a, BEAR))

    def test_without_it_a_creature_waits_for_your_turn(self):
        game, a, b = world([], hand=[BEAR], active=1)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST)]
        self.assertFalse(castable(game, a, BEAR))

    def test_only_creature_spells(self):
        game, a, b = world([VIVIEN], hand=[BEAR, DIVINATION], active=1)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(ISLAND), Permanent(ISLAND), Permanent(ISLAND)]
        self.assertEqual((castable(game, a, BEAR), castable(game, a, DIVINATION)), (True, False))

    def test_only_sorcery_spells(self):
        game, a, b = world([WIZARDS], hand=[BEAR, DIVINATION], active=1)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(ISLAND), Permanent(ISLAND), Permanent(ISLAND)]
        self.assertEqual((castable(game, a, BEAR), castable(game, a, DIVINATION)), (False, True))

    def test_only_spirits(self):
        game, a, b = world([SPIRITS], hand=[SPIRIT, BEAR], active=1)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(ISLAND)]
        self.assertEqual((castable(game, a, SPIRIT), castable(game, a, BEAR)), (True, False))

    def test_an_opponents_leyline_does_not_help_you(self):
        game, a, b = world([], theirs=[LEYLINE], hand=[BEAR], active=1)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST)]
        self.assertFalse(castable(game, a, BEAR))


class WhoMayCastTests(unittest.TestCase):
    def test_opponents_cannot_cast_during_your_turn(self):
        game, a, b = world(theirs=[KUTZIL], hand=[BOLT], active=1)  # b's turn: a is an opponent
        a.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",)))]
        self.assertFalse(castable(game, a, BOLT))
        game.active = 0  # a's own turn: the restriction is for b's turn only
        self.assertTrue(castable(game, a, BOLT))

    def test_the_controller_may_cast_on_their_own_turn(self):
        game, a, b = world([KUTZIL], hand=[BOLT], active=0)
        a.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",)))]
        self.assertTrue(castable(game, a, BOLT))

    def test_opponents_cannot_cast_during_combat_but_can_in_main_phase(self):
        game, a, b = world(theirs=[MARISI], hand=[BOLT], active=1, step="declare_blockers")
        a.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",)))]
        self.assertFalse(castable(game, a, BOLT))
        game.step = "main2"
        game.active = 0
        self.assertTrue(castable(game, a, BOLT))

    def test_the_controller_may_cast_in_combat(self):
        game, a, b = world([MARISI], hand=[BOLT], active=0, step="declare_blockers")
        a.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land \u2014 Mountain", produced_mana=("R",)))]
        self.assertTrue(castable(game, a, BOLT))

    def test_one_spell_each_turn_for_every_player(self):
        game, a, b = world([RULE_OF_LAW], hand=[BOLT, BOLT], active=0)
        a.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))) for _ in range(2)]
        self.assertTrue(castable(game, a, BOLT))
        a.cast_log.append((game.turn, BOLT))
        self.assertFalse(castable(game, a, BOLT))
        game.turn += 1
        self.assertTrue(castable(game, a, BOLT))

    def test_one_spell_each_turn_for_only_you(self):
        game, a, b = world([DEADLOCK], theirs=[], hand=[BOLT], active=0)
        a.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))) for _ in range(2)]
        a.cast_log.append((game.turn, BOLT))
        self.assertFalse(castable(game, a, BOLT))
        game2, a2, b2 = world([], theirs=[DEADLOCK], hand=[BOLT], active=0)  # an opponent's does not limit you
        a2.battlefield += [Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))) for _ in range(2)]
        a2.cast_log.append((game2.turn, BOLT))
        self.assertTrue(castable(game2, a2, BOLT))

    def test_you_cannot_cast_creature_spells(self):
        game, a, b = world([GOLEM], hand=[BEAR, DIVINATION], active=0)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(ISLAND), Permanent(ISLAND), Permanent(ISLAND)]
        self.assertEqual((castable(game, a, BEAR), castable(game, a, DIVINATION)), (False, True))

    def test_an_opponents_golem_does_not_stop_you(self):
        game, a, b = world([], theirs=[GOLEM], hand=[BEAR], active=0)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST)]
        self.assertTrue(castable(game, a, BEAR))

    def test_you_cannot_cast_noncreature_spells(self):
        game, a, b = world([NIKYA], hand=[BEAR, DIVINATION], active=0)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(ISLAND), Permanent(ISLAND), Permanent(ISLAND)]
        self.assertEqual((castable(game, a, BEAR), castable(game, a, DIVINATION)), (True, False))


class ActivationLockTests(unittest.TestCase):
    def test_artifacts_cannot_be_activated_by_anyone(self):
        game, _ = table3(pick(ACTIVATE))
        a, b = game.seats[0], game.seats[1]
        a.battlefield = [Permanent(LOOTER), Permanent(STONY)]
        a.battlefield[0].sick = False
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])
        a.battlefield = [Permanent(LOOTER)]
        self.assertTrue([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])

    def test_creatures_are_not_artifacts(self):
        game, _ = table3(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(Card(name="Healer", type_line="Creature \u2014 Cleric", power="1", toughness="1",
                                        oracle_text="{T}: You gain 1 life.")), Permanent(STONY)]
        a.battlefield[0].sick = False
        self.assertTrue([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])

    def test_an_artifacts_mana_ability_is_stopped_too_but_a_lands_is_not(self):
        game, a, b = world([STONY, SOL_RING], hand=[DIVINATION], active=0)
        self.assertFalse(castable(game, a, DIVINATION))  # Sol Ring would pay {C}{C}, but not with Stony Silence out
        a.battlefield.append(Permanent(ISLAND))
        a.battlefield.append(Permanent(ISLAND))
        a.battlefield.append(Permanent(ISLAND))
        self.assertTrue(castable(game, a, DIVINATION))

    def test_an_opponents_creatures_and_artifacts_cannot_make_mana_on_the_controllers_turn(self):
        game, a, b = world([ELF, SOL_RING], theirs=[ABOLISHER], active=1)
        a.battlefield[0].sick = False
        self.assertIsNone(game._payment(a, BEAR))  # the Elf and the ring are locked on b's turn
        a.battlefield += [Permanent(FOREST), Permanent(FOREST)]
        self.assertIsNotNone(game._payment(a, BEAR))  # lands still work

    def test_on_the_other_players_turn_it_does_not_apply(self):
        game, a, b = world([ELF, SOL_RING], theirs=[ABOLISHER], active=0)
        a.battlefield[0].sick = False
        self.assertIsNotNone(game._payment(a, BEAR))

    def test_its_controllers_own_permanents_are_free(self):
        game, a, b = world([ABOLISHER, ELF, SOL_RING], active=0)
        a.battlefield[1].sick = False
        self.assertIsNotNone(game._payment(a, BEAR))

    def test_it_stops_opponents_activating_abilities_of_creatures_on_that_turn(self):
        game, _ = table3(pick(ACTIVATE))
        a, b = game.seats[0], game.seats[1]
        a.battlefield = [Permanent(Card(name="Healer", type_line="Creature \u2014 Cleric", power="1", toughness="1",
                                        oracle_text="{T}: You gain 1 life."))]
        b.battlefield = [Permanent(ABOLISHER)]
        a.battlefield[0].sick = False
        game.active = 1
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])
        game.active = 0
        self.assertTrue([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])


class LandTypeTests(unittest.TestCase):
    def test_every_land_taps_for_black(self):
        game, a, b = world([URBORG], hand=[DARK], active=0)
        a.battlefield.append(Permanent(FOREST))
        self.assertTrue(castable(game, a, DARK))  # the Forest, and Urborg itself, are Swamps

    def test_without_it_a_forest_does_not(self):
        game, a, b = world([], hand=[DARK], active=0)
        a.battlefield.append(Permanent(FOREST))
        self.assertFalse(castable(game, a, DARK))

    def test_an_opponents_urborg_makes_your_lands_swamps_too(self):
        game, a, b = world([], theirs=[URBORG], hand=[DARK], active=0)
        a.battlefield.append(Permanent(FOREST))
        self.assertTrue(castable(game, a, DARK))

    def test_it_stops_when_urborg_leaves(self):
        game, a, b = world([URBORG], hand=[DARK], active=0)
        a.battlefield.append(Permanent(FOREST))
        a.battlefield.pop(0)
        self.assertFalse(castable(game, a, DARK))

    def test_a_forest_still_taps_for_green(self):
        game, a, b = world([URBORG], hand=[BEAR], active=0)
        a.battlefield.append(Permanent(FOREST))
        self.assertTrue(castable(game, a, BEAR))  # {1}{G}: the Forest makes G, Urborg {1}

    def test_each_land_is_a_forest(self):
        game, a, b = world([YAVIMAYA], hand=[BEAR], active=0)
        a.battlefield.append(Permanent(ISLAND))
        self.assertTrue(castable(game, a, BEAR))

    def test_every_basic_land_type_for_the_controller_only(self):
        game, a, b = world([DRYAD], hand=[DIVINATION], active=0)
        a.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(FOREST)]
        self.assertTrue(castable(game, a, DIVINATION))  # Forests make {U}
        game2, a2, b2 = world([], theirs=[DRYAD], hand=[DIVINATION], active=0)
        a2.battlefield += [Permanent(FOREST), Permanent(FOREST), Permanent(FOREST)]
        self.assertFalse(castable(game2, a2, DIVINATION))


class ReportTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for c in (URBORG, YAVIMAYA, RHYTHM, SQUELCHER, LEYLINE, VIVIEN, KUTZIL, MARISI, RULE_OF_LAW, DEADLOCK, GOLEM, NIKYA, ABOLISHER,
                  STONY):
            with self.subTest(c.name):
                self.assertEqual(unsupported_lines(c), [])


if __name__ == "__main__":
    unittest.main()
