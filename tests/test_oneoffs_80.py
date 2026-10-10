"""The one-off lines of issue #80 that no other card shares (Blossoming Bogbeast first). Lines are the cards' own Oracle text from
Scryfall; each has cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import activate, fire
from tests.test_x_targets import script
from infernal_machine.effects import CONTRACT_TEXT
from tests.test_triggers_80 import FOREST, RELIC, SHRINE, card

BOGBEAST = Card(name="Blossoming Bogbeast", mana_cost="{4}{G}", type_line="Creature — Beast", power="5", toughness="5",
                oracle_text="Whenever this creature attacks, you gain 2 life. Then creatures you control gain trample and get +X/+X "
                            "until end of turn, where X is the amount of life you gained this turn.")


class BlossomingBogbeastTests(unittest.TestCase):
    def attack(self, gained_before=0):
        game, _ = table3(pick())
        a = game.seats[0]
        self.beast, self.bear = Permanent(BOGBEAST), Permanent(BEAR)
        a.battlefield = [self.beast, self.bear]
        if gained_before:
            game.change_life(a, gained_before)
        fire(game, a, self.beast, "attacks")
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(BOGBEAST), [])

    def test_it_gains_two_life_and_every_creature_gets_plus_two(self):
        game, a = self.attack()
        self.assertEqual((a.life, game.power(self.beast), game.power(self.bear)), (42, 7, 4))
        self.assertTrue(game.has_keyword(self.bear, "trample"))

    def test_the_bonus_counts_all_the_life_gained_this_turn(self):
        game, a = self.attack(gained_before=3)
        self.assertEqual((game.power(self.beast), game.power(self.bear)), (10, 7))  # 3 + 2


ANGER = Card(name="Anger", mana_cost="{3}{R}", type_line="Creature — Incarnation", power="2", toughness="2",
             oracle_text="Haste\nAs long as this card is in your graveyard and you control a Mountain, creatures you control have haste.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))


class AngerTests(unittest.TestCase):
    def table(self, graveyard=(), battlefield=()):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.bear = Permanent(BEAR, sick=True)
        a.battlefield = [self.bear, *battlefield]
        a.graveyard = list(graveyard)
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(ANGER), [])

    def test_in_the_graveyard_with_a_mountain_your_creatures_have_haste(self):
        game, a, b = self.table([ANGER], [Permanent(MOUNTAIN)])
        self.assertTrue(game.has_keyword(self.bear, "haste"))

    def test_without_a_mountain_it_does_nothing(self):
        game, a, b = self.table([ANGER], [Permanent(FOREST)])
        self.assertFalse(game.has_keyword(self.bear, "haste"))

    def test_on_the_battlefield_it_gives_no_haste_to_others(self):
        game, a, b = self.table([], [Permanent(ANGER), Permanent(MOUNTAIN)])
        self.assertFalse(game.has_keyword(self.bear, "haste"))

    def test_in_an_opponents_graveyard_it_does_nothing_for_you(self):
        game, a, b = self.table([], [Permanent(MOUNTAIN)])
        b.graveyard = [ANGER]
        self.assertFalse(game.has_keyword(self.bear, "haste"))

    def test_it_works_for_the_graveyard_owner_only(self):
        game, a, b = self.table([], [])
        theirs = Permanent(BEAR, sick=True)
        b.battlefield = [theirs, Permanent(MOUNTAIN)]
        b.graveyard = [ANGER]
        self.assertEqual((game.has_keyword(theirs, "haste"), game.has_keyword(self.bear, "haste")), (True, False))

    def test_it_stops_when_the_card_leaves_the_graveyard(self):
        game, a, b = self.table([ANGER], [Permanent(MOUNTAIN)])
        a.graveyard = []
        self.assertFalse(game.has_keyword(self.bear, "haste"))


COMMAND = Card(name="Quandrix Command", mana_cost="{1}{G}{U}", cmc=3.0, type_line="Instant",
               oracle_text="Choose two —\n• Return target creature or planeswalker to its owner's hand.\n• Counter target "
                           "artifact or enchantment spell.\n• Put two +1/+1 counters on target creature.\n• Target player "
                           "shuffles up to three target cards from their graveyard into their library.")


class QuandrixCommandTests(unittest.TestCase):
    def cast(self, graveyard, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.bear = Permanent(BEAR)
        a.battlefield = [self.bear] + lands(3)
        a.hand = [COMMAND]
        a.graveyard = list(graveyard)
        a.library = [FOREST] * 5
        game._perform(a, CAST + "Quandrix Command")
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(COMMAND), [])

    def test_up_to_three_cards_are_shuffled_into_the_library(self):
        game, a = self.cast([RELIC, SHRINE, FOREST, OGRE_CARD], "Put two", "Target player", "Relic", "Shrine", "Forest", "Ogre")
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Ogre", "Quandrix Command"])
        self.assertEqual(len(a.library), 8)

    def test_it_pairs_with_the_counter_mode(self):
        game, a = self.cast([RELIC], "Put two", "Target player", "Bear", "Relic")
        self.assertEqual((self.bear.counters.get("+1/+1"), [c.name for c in a.graveyard]), (2, ["Quandrix Command"]))

    def test_it_may_shuffle_nothing(self):
        game, a = self.cast([RELIC], "Put two", "Target player", "Bear", "No target")
        self.assertEqual([c.name for c in a.graveyard], ["Relic", "Quandrix Command"])


OGRE_CARD = Card(name="Ogre", mana_cost="{3}", cmc=3.0, type_line="Creature — Ogre", power="3", toughness="3")


from infernal_machine.game import CAST_COMMANDER  # noqa: E402

OPAL_PALACE = Card(name="Opal Palace", type_line="Land", oracle_text="{T}: Add {C}.\n{1}, {T}: Add one mana of any color in your commander's "
                   "color identity. If you spend this mana to cast your commander, it enters with a number of additional +1/+1 counters "
                   "on it equal to the number of times it's been cast from the command zone this game.")
WHITE_COMMANDER = Card(name="Zada", mana_cost="{W}", cmc=1.0, type_line="Legendary Creature — Goblin", power="1", toughness="1",
                       colors=("W",))


class OpalPalaceTests(unittest.TestCase):
    def table(self, casts):
        game, _ = table3(pick())
        a = game.seats[0]
        a.command_zone, a.commander_names, a.color_identity = [WHITE_COMMANDER], {WHITE_COMMANDER.name}, frozenset("W")
        a.battlefield = [Permanent(OPAL_PALACE), Permanent(FOREST), Permanent(FOREST), Permanent(FOREST)]
        if casts:
            a.commander_casts[WHITE_COMMANDER.name] = casts
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(OPAL_PALACE), [])

    def test_the_commander_enters_with_a_counter_for_each_time_it_was_cast(self):
        game, a = self.table(casts=1)  # this is the second cast
        game._perform(a, CAST_COMMANDER + "Zada")
        run_stack(game)
        zada = next(p for p in a.battlefield if p.card.name == "Zada")
        self.assertEqual(zada.counters.get("+1/+1"), 2)  # it has now been cast twice

    def test_the_first_cast_gives_one(self):
        game, a = self.table(casts=0)
        game._perform(a, CAST_COMMANDER + "Zada")
        run_stack(game)
        zada = next(p for p in a.battlefield if p.card.name == "Zada")
        self.assertEqual(zada.counters.get("+1/+1"), 1)

    def test_mana_spent_on_something_else_gives_no_counters(self):
        game, a = self.table(casts=1)
        a.hand = [BEAR_WHITE]
        game._perform(a, CAST + "Pale Bear")
        run_stack(game)
        bear = next(p for p in a.battlefield if p.card.name == "Pale Bear")
        self.assertIsNone(bear.counters.get("+1/+1"))

    def test_the_plain_mana_does_not_count(self):
        game, a = self.table(casts=1)
        a.battlefield = [Permanent(OPAL_PALACE)] + [Permanent(Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",)))] * 3
        game._perform(a, CAST_COMMANDER + "Zada")  # the palace's {C} pays the generic tax; no filter mana is made
        run_stack(game)
        zada = next(p for p in a.battlefield if p.card.name == "Zada")
        self.assertIsNone(zada.counters.get("+1/+1"))


BEAR_WHITE = Card(name="Pale Bear", mana_cost="{1}{W}", cmc=2.0, type_line="Creature — Bear", power="2", toughness="2", colors=("W",))


PRODIGY = Card(name="Harmonic Prodigy", mana_cost="{1}{R}", cmc=2.0, type_line="Creature — Human Wizard", power="1", toughness="3",
               oracle_text="Prowess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)\nIf a triggered "
                           "ability of a Shaman or another Wizard you control triggers, that ability triggers an additional time.")
WIZARD_DRAWER = Card(name="Scholar", mana_cost="{1}{U}", cmc=2.0, type_line="Creature — Human Wizard", power="1", toughness="1",
                     oracle_text="When this creature enters, draw a card.")
SHAMAN_WATCHER = Card(name="Shaman Watcher", mana_cost="{1}{R}", cmc=2.0, type_line="Creature — Goblin Shaman", power="1", toughness="1",
                      oracle_text="Whenever you cast an instant or sorcery spell, you gain 1 life.")
OGRE_DRAWER = Card(name="Brute", mana_cost="{3}", cmc=3.0, type_line="Creature — Ogre", power="3", toughness="3",
                   oracle_text="When this creature enters, draw a card.")


class HarmonicProdigyTests(unittest.TestCase):
    def table(self, *others):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in others]
        a.library = [FOREST] * 10
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(PRODIGY), [])

    def test_another_wizard_triggers_an_additional_time(self):
        game, a = self.table(PRODIGY)
        game._enter(a, Permanent(WIZARD_DRAWER))
        run_stack(game)
        self.assertEqual(len(a.hand), 2)

    def test_a_shaman_triggers_an_additional_time(self):
        game, a = self.table(PRODIGY, SHAMAN_WATCHER)
        a.cast_log.append((game.turn, STUDY_SPELL))
        game._observe("cast", STUDY_SPELL, a)
        run_stack(game)
        self.assertEqual(a.life, 42)

    def test_a_creature_that_is_neither_triggers_once(self):
        game, a = self.table(PRODIGY)
        game._enter(a, Permanent(OGRE_DRAWER))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_without_the_prodigy_a_wizard_triggers_once(self):
        game, a = self.table()
        game._enter(a, Permanent(WIZARD_DRAWER))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_the_prodigys_own_triggers_do_not_double(self):
        game, a = self.table()
        prodigy_drawer = Card(name="Prodigy", type_line="Creature — Human Wizard", power="1", toughness="1",
                              oracle_text="When this creature enters, draw a card.\nIf a triggered ability of a Shaman or another Wizard "
                                          "you control triggers, that ability triggers an additional time.")
        game._enter(a, Permanent(prodigy_drawer))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_two_prodigies_add_two_extra_triggers(self):
        game, a = self.table(PRODIGY, PRODIGY)
        game._enter(a, Permanent(WIZARD_DRAWER))
        run_stack(game)
        self.assertEqual(len(a.hand), 3)

    def test_an_opponents_prodigy_does_nothing_for_you(self):
        game, a = self.table()
        game.seats[1].battlefield = [Permanent(PRODIGY)]
        game._enter(a, Permanent(WIZARD_DRAWER))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)


STUDY_SPELL = Card(name="Spark", mana_cost="{R}", cmc=1.0, type_line="Instant")


ANCIENT = Card(name="Forgotten Ancient", mana_cost="{3}{G}", cmc=4.0, type_line="Creature — Elemental", power="0", toughness="3",
               oracle_text="Whenever a player casts a spell, you may put a +1/+1 counter on this creature.\nAt the beginning of your "
                           "upkeep, you may move any number of +1/+1 counters from this creature onto other creatures.")


class ForgottenAncientTests(unittest.TestCase):
    def upkeep(self, counters, *choices):
        game, _ = table3(script(*choices))
        a, b, _ = game.seats
        self.ancient = Permanent(ANCIENT, counters={"+1/+1": counters} if counters else {})
        self.bear, self.ogre = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [self.ancient, self.bear]
        b.battlefield = [self.ogre]
        fire(game, a, self.ancient, "upkeep")
        return game, a

    def count(self, p):
        return p.counters.get("+1/+1", 0)

    def test_parse(self):
        self.assertEqual(unsupported_lines(ANCIENT), [])

    def test_counters_move_onto_another_creature(self):
        game, a = self.upkeep(4, "Yes", "3", "Bear")
        self.assertEqual((self.count(self.ancient), self.count(self.bear)), (1, 3))

    def test_they_can_be_split_among_creatures(self):
        game, a = self.upkeep(4, "Yes", "1", "Bear", "3", "Ogre")
        self.assertEqual((self.count(self.ancient), self.count(self.bear), self.count(self.ogre)), (0, 1, 3))

    def test_moving_none_leaves_them(self):
        game, a = self.upkeep(4, "Yes", "0")
        self.assertEqual((self.count(self.ancient), self.count(self.bear)), (4, 0))

    def test_declining_leaves_them(self):
        game, a = self.upkeep(4, "No")
        self.assertEqual((self.count(self.ancient), self.count(self.bear)), (4, 0))

    def test_with_no_counters_nothing_happens(self):
        game, a = self.upkeep(0, "Yes", "1", "Bear")
        self.assertEqual(self.count(self.bear), 0)

    def test_it_never_moves_counters_onto_itself(self):
        game, a = self.upkeep(2, "Yes", "2", "Forgotten")  # not offered: the first creature listed gets them
        self.assertEqual((self.count(self.ancient), self.count(self.bear)), (0, 2))


BREW = Card(name="Deadly Brew", mana_cost="{B}{G}", cmc=2.0, type_line="Sorcery",
            oracle_text="Each player sacrifices a creature or planeswalker of their choice. If you sacrificed a permanent this way, you "
                        "may return another permanent card from your graveyard to your hand.")
WALKER = Card(name="Walker", mana_cost="{3}", cmc=3.0, type_line="Legendary Planeswalker — Test", loyalty="4")


class DeadlyBrewTests(unittest.TestCase):
    def cast(self, mine, theirs, graveyard, *choices):
        game, _ = table3(script(*choices))
        a, b, c = game.seats
        a.battlefield = [Permanent(x) for x in mine] + lands(2)
        b.battlefield = [Permanent(x) for x in theirs]
        a.graveyard = list(graveyard)
        a.hand = [BREW]
        game._perform(a, CAST + "Deadly Brew")
        run_stack(game)
        return game, a, b, c

    def test_parse(self):
        self.assertEqual(unsupported_lines(BREW), [])

    def test_each_player_sacrifices_and_you_return_another_permanent_card(self):
        game, a, b, c = self.cast([BEAR], [OGRE], [RELIC, SHRINE], "Bear", "Ogre", "Relic")
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name in ("Bear",)], [])
        self.assertEqual(b.battlefield, [])
        self.assertEqual([x.name for x in a.hand], ["Relic"])

    def test_a_planeswalker_may_be_the_sacrifice(self):
        game, a, b, c = self.cast([WALKER], [], [RELIC], "Walker", "Relic")
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Walker"], [])
        self.assertEqual([x.name for x in a.hand], ["Relic"])

    def test_if_you_had_nothing_to_sacrifice_you_return_nothing(self):
        game, a, b, c = self.cast([], [OGRE], [RELIC], "Ogre", "Relic")
        self.assertEqual((b.battlefield, a.hand), ([], []))

    def test_the_card_you_sacrificed_is_not_another_card(self):
        game, a, b, c = self.cast([BEAR], [], [], "Bear", "Bear")
        self.assertEqual(a.hand, [])  # only the Bear is in the graveyard, and it is not "another"

    def test_the_return_is_optional(self):
        game, a, b, c = self.cast([BEAR], [], [RELIC], "Bear", "Take none")
        self.assertEqual(a.hand, [])


PRIEST = Card(name="Priest of Forgotten Gods", mana_cost="{1}{B}", cmc=2.0, type_line="Creature — Human Cleric", power="2", toughness="2",
              oracle_text="{T}, Sacrifice two other creatures: Any number of target players each lose 2 life and sacrifice a creature of "
                          "their choice. You add {B}{B} and draw a card. (Activate only as an instant.)")


class PriestOfForgottenGodsTests(unittest.TestCase):
    def table(self, mine=(BEAR, BEAR), theirs=(OGRE,)):
        game, _ = table3(script("Yes"))
        a, b, c = game.seats
        self.priest = Permanent(PRIEST, sick=False)
        a.battlefield = [self.priest] + [Permanent(x) for x in mine]
        b.battlefield = [Permanent(x) for x in theirs]
        a.library = [FOREST] * 5
        return game, a, b, c

    def activate(self, game, a, *answers):
        game.seats[0].player.policy = script(*answers)
        activate(game, a, "Any number of target players")
        run_stack(game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(PRIEST), [])

    def test_the_targeted_players_lose_life_and_sacrifice_and_you_get_mana_and_a_card(self):
        game, a, b, c = self.table(theirs=(OGRE,))
        self.activate(game, a, "Player: B", "Player: C", "No target", "Bear", "Bear")
        self.assertEqual((b.life, c.life, b.battlefield), (38, 38, []))
        self.assertEqual(sorted("".join(sorted(u)) for u in a.mana_pool), ["B", "B"])
        self.assertEqual(len(a.hand), 1)
        self.assertEqual([p.card.name for p in a.battlefield], ["Priest of Forgotten Gods"])  # both Bears were the cost

    def test_it_can_target_no_one_and_still_pays_out(self):
        game, a, b, c = self.table()
        self.activate(game, a, "No target", "Bear", "Bear")
        self.assertEqual((b.life, len(a.mana_pool), len(a.hand)), (40, 2, 1))

    def test_it_needs_two_other_creatures(self):
        game, a, b, c = self.table(mine=(BEAR,))
        self.assertFalse([x for x in game.legal_actions(a) if "Any number of target players" in x])


PLUMB = Card(name="Plumb the Forbidden", mana_cost="{1}{B}", cmc=2.0, type_line="Instant",
             oracle_text="As an additional cost to cast this spell, you may sacrifice one or more creatures. When you do, copy this spell "
                         "for each creature sacrificed this way.\nYou draw a card and lose 1 life.")


class PlumbTheForbiddenTests(unittest.TestCase):
    def cast(self, creatures, sacrifice):
        game, _ = table3(script(str(sacrifice)))
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR) for _ in range(creatures)] + lands(2)
        a.hand = [PLUMB]
        a.library = [FOREST] * 10
        game._perform(a, CAST + "Plumb the Forbidden")
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(PLUMB), [])

    def test_with_no_sacrifice_it_is_just_the_spell(self):
        game, a = self.cast(3, 0)
        self.assertEqual((len(a.hand), a.life, len([p for p in a.battlefield if p.card.name == "Bear"])), (1, 39, 3))

    def test_each_creature_sacrificed_adds_a_copy(self):
        game, a = self.cast(3, 2)
        self.assertEqual((len(a.hand), a.life), (3, 37))  # the spell and two copies each draw a card and cost a life
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Bear"]), 1)

    def test_with_no_creatures_nothing_is_offered(self):
        game, a = self.cast(0, 0)
        self.assertEqual(len(a.hand), 1)


WARD = Card(name="Flickering Ward", mana_cost="{W}", cmc=1.0, type_line="Enchantment — Aura", colors=("W",),
            oracle_text="Enchant creature\nAs this Aura enters, choose a color.\nEnchanted creature has protection from the chosen color. "
                        "This effect doesn't remove this Aura.\n{W}: Return this Aura to its owner's hand.")
MUTATION = Card(name="Darksteel Mutation", mana_cost="{1}{W}", cmc=2.0, type_line="Enchantment — Aura", colors=("W",),
                oracle_text="Enchant creature\nEnchanted creature is an Insect artifact creature with base power and toughness 0/1 and "
                            "has indestructible, and it loses all other abilities, card types, and creature types.")
SHOCK_RED = frozenset({"R"})


class FlickeringWardTests(unittest.TestCase):
    def table(self, color):
        game, _ = table3(pick(color))
        a = game.seats[0]
        self.bear = Permanent(BEAR)
        a.battlefield = [self.bear] + lands(1)
        self.ward = Permanent(WARD, sick=True, attached_to=self.bear)
        game._enter(a, self.ward)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(WARD), [])

    def test_the_creature_has_protection_from_the_chosen_color(self):
        game, a = self.table("Red")
        self.assertTrue(game.protected_from(self.bear, SHOCK_RED))
        self.assertFalse(game.protected_from(self.bear, frozenset({"U"})))

    def test_the_choice_decides_which_color(self):
        game, a = self.table("Blue")
        self.assertTrue(game.protected_from(self.bear, frozenset({"U"})))
        self.assertFalse(game.protected_from(self.bear, SHOCK_RED))

    def test_a_chosen_white_does_not_knock_the_white_aura_off(self):
        game, a = self.table("White")
        game._check_state()
        self.assertIs(self.ward.attached_to, self.bear)
        self.assertIn(self.ward, a.battlefield)

    def test_it_can_return_itself_to_its_owners_hand(self):
        game, a = self.table("Red")
        activate(game, a, "Return this Aura")
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [p.card.name for p in a.battlefield if p.card.name == "Flickering Ward"]),
                         (["Flickering Ward"], []))


class DarksteelMutationTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a = game.seats[0]
        self.dragon = Permanent(Card(name="Dragon", type_line="Creature — Dragon", power="5", toughness="5", oracle_text="Flying, haste"))
        a.battlefield = [self.dragon]
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(MUTATION), [])

    def test_it_becomes_a_0_1_indestructible_without_abilities(self):
        game, a = self.table()
        a.battlefield.append(Permanent(MUTATION, attached_to=self.dragon))
        self.assertEqual((game.power(self.dragon), game.toughness(self.dragon)), (0, 1))
        self.assertTrue(game.has_keyword(self.dragon, "indestructible"))
        self.assertFalse(game.has_keyword(self.dragon, "flying"))

    def test_without_it_the_creature_is_unchanged(self):
        game, a = self.table()
        self.assertEqual((game.power(self.dragon), game.has_keyword(self.dragon, "flying")), (5, True))


ARROGANCE = Card(name="Tragic Arrogance", mana_cost="{3}{W}{W}", cmc=5.0, type_line="Sorcery",
                 oracle_text="For each player, you choose from among the permanents that player controls an artifact, a creature, an "
                             "enchantment, and a planeswalker. Then each player sacrifices all other nonland permanents they control.")
GLORY = Card(name="Glory", mana_cost="{2}", cmc=2.0, type_line="Enchantment")


class TragicArroganceTests(unittest.TestCase):
    def cast(self, mine, theirs, *choices):
        game, _ = table3(script(*choices))
        a, b, c = game.seats
        a.battlefield = [Permanent(x) for x in mine] + lands(5)
        b.battlefield = [Permanent(x) for x in theirs]
        a.hand = [ARROGANCE]
        game._perform(a, CAST + "Tragic Arrogance")
        run_stack(game)
        game._check_state()
        return game, a, b

    def names(self, seat):
        return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)

    def test_parse(self):
        self.assertEqual(unsupported_lines(ARROGANCE), [])

    def test_each_player_keeps_one_of_each_type_the_caster_chooses(self):
        game, a, b = self.cast([BEAR, OGRE, RELIC, RELIC, GLORY], [BEAR, OGRE, WALKER, GLORY],
                               "Relic", "Ogre", "Bear")  # A's artifact and creature, then B's creature
        self.assertEqual(self.names(a), ["Glory", "Ogre", "Relic"])
        self.assertEqual(self.names(b), ["Bear", "Glory", "Walker"])

    def test_lands_are_never_sacrificed(self):
        game, a, b = self.cast([BEAR], [FOREST_PERMANENT_CARD])
        self.assertEqual(len([p for p in b.battlefield if "Land" in p.card.type_line]), 1)
        self.assertEqual(len([p for p in a.battlefield if "Land" in p.card.type_line]), 5)

    def test_the_opponents_pay_too(self):
        game, a, b = self.cast([BEAR], [BEAR, OGRE, BEAR], "Bear", "Ogre")
        self.assertEqual(len(b.battlefield), 1)

    def test_a_type_with_no_permanent_keeps_nothing(self):
        game, a, b = self.cast([BEAR], [GLORY])
        self.assertEqual(self.names(b), ["Glory"])


FOREST_PERMANENT_CARD = FOREST


SCRIV = Card(name="Scriv, the Obligator", mana_cost="{2}{W}{B}", cmc=4.0, type_line="Legendary Creature — Inkling Bird", power="3", toughness="3",
             colors=("W", "B"),
             oracle_text="Flying, deathtouch\nWhenever Scriv enters or attacks, create a white Aura enchantment token named Contract "
                         "attached to target creature an opponent controls. The token has enchant creature and \"Whenever enchanted "
                         "creature attacks, it gets +2/+0 until end of turn if it's attacking one of your opponents. Otherwise, its "
                         "controller loses 2 life.\"")


class ScrivTests(unittest.TestCase):
    def table(self, *answers):
        game, _ = table3(script(*answers))
        a, b, c = game.seats
        self.scriv = Permanent(SCRIV)
        self.theirs = Permanent(OGRE, sick=False)
        a.battlefield = [self.scriv]
        b.battlefield = [self.theirs]
        return game, a, b, c

    def contracts(self, game):
        return [p for s in game.seats for p in s.battlefield if p.card.name == "Contract"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(SCRIV), [])

    def test_entering_puts_a_contract_on_an_opponents_creature(self):
        game, a, b, c = self.table("Ogre")
        fire(game, a, self.scriv, "enters")
        [contract] = self.contracts(game)
        self.assertIs(contract.attached_to, self.theirs)
        self.assertEqual((contract.card.type_line, contract.card.colors), ("Token Enchantment — Aura", ("W",)))
        self.assertIn(contract, a.battlefield)  # Scriv's controller controls the Aura

    def test_attacking_does_it_again(self):
        game, a, b, c = self.table("Ogre", "Ogre")
        fire(game, a, self.scriv, "enters")
        fire(game, a, self.scriv, "attacks")
        self.assertEqual(len(self.contracts(game)), 2)

    def test_the_enchanted_creature_attacking_one_of_the_controllers_opponents_gets_plus_two(self):
        game, a, b, c = self.table("Ogre")
        fire(game, a, self.scriv, "enters")
        [contract] = self.contracts(game)
        game.trigger("host_attacks", contract, a, self.theirs, x=2)  # B's Ogre attacks C, an opponent of A
        run_stack(game)
        self.assertEqual((game.power(self.theirs), b.life), (5, 40))

    def test_attacking_the_controller_costs_its_controller_two_life(self):
        game, a, b, c = self.table("Ogre")
        fire(game, a, self.scriv, "enters")
        [contract] = self.contracts(game)
        game.trigger("host_attacks", contract, a, self.theirs, x=0)  # B's Ogre attacks A
        run_stack(game)
        self.assertEqual((game.power(self.theirs), b.life), (3, 38))

    def test_in_real_combat_an_attack_on_a_third_player_gets_plus_two(self):
        policy = lambda prompt, options: 2 if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(None, policy)
        a, b, c = game.seats
        theirs = Permanent(OGRE, sick=False)
        b.battlefield = [theirs]
        a.battlefield = [Permanent(Card(name="Contract", type_line="Token Enchantment \u2014 Aura", colors=("W",), oracle_text=CONTRACT_TEXT),
                                 attached_to=theirs)]
        game.active = 1
        game.combat.declare_attackers(b)  # option 2 is seat 2, an opponent of the Aura's controller
        run_stack(game)
        self.assertEqual((game.power(theirs), b.life), (5, 40))

    def test_in_real_combat_the_defender_is_passed(self):
        picks = iter([1])
        policy = lambda prompt, options: next(picks) if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(None, policy)
        a, b, c = game.seats
        theirs = Permanent(OGRE, sick=False)
        b.battlefield = [theirs]
        a.battlefield = [Permanent(Card(name="Contract", type_line="Token Enchantment — Aura", colors=("W",),
                                        oracle_text="Enchant creature\nWhenever enchanted creature attacks, it gets +2/+0 until end of turn if it's "
                                                    "attacking one of your opponents. Otherwise, its controller loses 2 life."),
                                 attached_to=theirs)]
        game.active = 1
        game.combat.declare_attackers(b)  # option 1 is seat 0: the Aura's controller
        run_stack(game)
        self.assertEqual(b.life, 38)
