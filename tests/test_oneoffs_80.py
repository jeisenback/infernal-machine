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
