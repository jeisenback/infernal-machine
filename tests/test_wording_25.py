"""Wording of real Oracle text that the engine missed when the five precon decks were checked against Scryfall (#25).
Each line is the card's own text; every fix has a case where it must not apply.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import FOREST, lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire

PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
TOWER = Card(name="Command Tower", type_line="Land", produced_mana=("W", "U", "B", "R", "G"))

LAND_TAX = Card(name="Land Tax", mana_cost="{W}", type_line="Enchantment",
                oracle_text="At the beginning of your upkeep, if an opponent controls more lands than you, you may search your "
                            "library for up to three basic land cards, reveal them, put them into your hand, then shuffle.")
TROPHY = Card(name="Assassin's Trophy", mana_cost="{B}{G}", cmc=2.0, type_line="Instant",
              oracle_text="Destroy target permanent an opponent controls. Its controller may search their library for a basic "
                          "land card, put it onto the battlefield, then shuffle.")


def names(cards):
    return sorted(c.name for c in cards)


class LandTaxTests(unittest.TestCase):
    def upkeep(self, answer, library, mine=0, theirs=2):
        game, _ = table3(pick(answer))
        a, b, _ = game.seats
        tax = Permanent(LAND_TAX)
        a.battlefield = [tax, *lands(mine)]
        b.battlefield = lands(theirs)
        a.library = list(library)
        fire(game, a, tax, "upkeep")
        return a

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(LAND_TAX), [])

    def test_up_to_three_basic_lands_go_to_the_hand(self):
        a = self.upkeep("Yes", [FOREST, PLAINS, FOREST, FOREST, BEAR])
        self.assertEqual((names(a.hand), len(a.library)), (["Forest", "Forest", "Plains"], 2))

    def test_fewer_basics_than_three_takes_what_there_is(self):
        a = self.upkeep("Yes", [FOREST, BEAR, BEAR])
        self.assertEqual(names(a.hand), ["Forest"])

    def test_a_nonbasic_land_is_not_taken(self):
        a = self.upkeep("Yes", [TOWER, TOWER, TOWER, FOREST])
        self.assertEqual(names(a.hand), ["Forest"])

    def test_declining_takes_nothing(self):
        a = self.upkeep("No", [FOREST, FOREST, FOREST])
        self.assertEqual(a.hand, [])

    def test_nothing_happens_if_no_opponent_has_more_lands(self):
        a = self.upkeep("Yes", [FOREST, FOREST, FOREST], mine=2, theirs=2)
        self.assertEqual(a.hand, [])

    def test_the_library_is_shuffled_afterwards(self):
        a = self.upkeep("Yes", [FOREST, FOREST, FOREST] + [BEAR] * 30)
        self.assertEqual(sorted(c.name for c in a.library), ["Bear"] * 30)


class AssassinsTrophyTests(unittest.TestCase):
    def cast(self, answer, library):
        game, _, _ = table(pick(CAST, "Ogre"), pick(answer))
        a, b = game.seats
        a.hand, a.battlefield = [TROPHY], lands(2)
        victim = Permanent(OGRE)
        b.battlefield = [victim]
        b.library = list(library)
        game._priority_round(a)
        return a, b, victim

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(TROPHY), [])

    def test_the_victims_controller_gets_an_untapped_basic_land(self):
        a, b, victim = self.cast("Yes", [BEAR, FOREST])
        self.assertEqual([(p.card.name, p.tapped) for p in b.battlefield], [("Forest", False)])

    def test_the_search_is_optional(self):
        a, b, victim = self.cast("No", [FOREST])
        self.assertEqual(b.battlefield, [])

    def test_the_caster_gets_no_land(self):
        a, b, victim = self.cast("Yes", [FOREST])
        self.assertEqual(sum("Land" in p.card.type_line and p.card.name == "Forest" for p in a.battlefield), 0)

    def test_the_permanent_is_destroyed(self):
        a, b, victim = self.cast("Yes", [FOREST])
        self.assertNotIn(victim, b.battlefield)


PAWN = Card(name="Pawn of Ulamog", mana_cost="{2}{B}", type_line="Creature — Vampire Shaman", power="2", toughness="2",
            oracle_text='Whenever this creature or another nontoken creature you control dies, you may create a 0/1 colorless '
                        'Eldrazi Spawn creature token. It has "Sacrifice this token: Add {C}."')
ROAST = Card(name="Ribtruss Roaster", mana_cost="{3}{B}", type_line="Creature — Insect", power="3", toughness="3",
             oracle_text='At the beginning of your end step, create a number of 1/1 black and green Pest creature tokens equal to '
                         'the number of +1/+1 counters on this creature. They have "When this token dies, you gain 1 life."')
RESCUER = Card(name="Pest Rescuer", mana_cost="{2}{B}", type_line="Creature — Pest", power="2", toughness="2",
               oracle_text='At the beginning of each upkeep, if you don\'t control a Pest creature token, create a 1/1 black and '
                           'green Pest creature token with "When this token dies, you gain 1 life."')
PEST = Card(name="Pest", type_line="Token Creature — Pest", power="1", toughness="1", colors=("B", "G"),
            oracle_text="When this token dies, you gain 1 life.")
SPAWN_CARD = Card(name="Spawn Keeper", type_line="Creature — Eldrazi Pest", power="1", toughness="1")  # a card, not a token


def kill(game, *permanents):
    game._leave_together([(p, "destroyed") for p in permanents])
    run_stack(game)


class PawnOfUlamogTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(pick("Yes"))
        self.a, self.b, _ = self.game.seats
        self.pawn = Permanent(PAWN)
        self.a.battlefield = [self.pawn]

    def spawns(self, seat=None):
        return [p for p in (seat or self.a).battlefield if p.card.name == "Eldrazi Spawn"]

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(PAWN), [])

    def test_another_nontoken_creature_dying_makes_a_spawn_that_sacrifices_for_mana(self):
        other = Permanent(BEAR)
        self.a.battlefield.append(other)
        kill(self.game, other)
        [spawn] = self.spawns()
        self.assertEqual((spawn.card.power, spawn.card.toughness), ("0", "1"))
        self.assertIn("Sacrifice this token: Add {C}.", spawn.card.oracle_text)

    def test_it_dying_makes_one_too(self):
        kill(self.game, self.pawn)
        self.assertEqual(len(self.spawns()), 1)

    def test_a_token_dying_does_not(self):
        token = Permanent(PEST)
        self.a.battlefield.append(token)
        kill(self.game, token)
        self.assertEqual(self.spawns(), [])

    def test_an_opponents_creature_dying_does_not(self):
        other = Permanent(BEAR)
        self.b.battlefield = [other]
        kill(self.game, other)
        self.assertEqual(self.spawns(), [])

    def test_declining_makes_none(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        pawn, other = Permanent(PAWN), Permanent(BEAR)
        a.battlefield = [pawn, other]
        kill(game, other)
        self.assertEqual([p for p in a.battlefield if p.card.name == "Eldrazi Spawn"], [])


class RibtrussRoasterTests(unittest.TestCase):
    def end_step(self, counters):
        game, _ = table3()
        a = game.seats[0]
        roaster = Permanent(ROAST, counters={"+1/+1": counters} if counters else {})
        a.battlefield = [roaster]
        fire(game, a, roaster, "end_step")
        return game, a

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(ROAST), [])

    def test_one_pest_for_each_counter(self):
        game, a = self.end_step(3)
        pests = [p for p in a.battlefield if p.card.name == "Pest"]
        self.assertEqual(len(pests), 3)

    def test_no_counters_means_no_pests(self):
        game, a = self.end_step(0)
        self.assertEqual([p for p in a.battlefield if p.card.name == "Pest"], [])

    def test_each_pest_gains_life_when_it_dies(self):
        game, a = self.end_step(2)
        a.life = 20
        pest = next(p for p in a.battlefield if p.card.name == "Pest")
        kill(game, pest)
        self.assertEqual(a.life, 21)


class PestRescuerTests(unittest.TestCase):
    def upkeep(self, mine=(), theirs=()):
        game, _ = table3()
        a, b, _ = game.seats
        rescuer = Permanent(RESCUER)
        a.battlefield = [rescuer, *[Permanent(c) for c in mine]]
        b.battlefield = [Permanent(c) for c in theirs]
        fire(game, a, rescuer, "each_upkeep")
        return [p for p in a.battlefield if p.card.name == "Pest"]

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(RESCUER), [])

    def test_it_makes_a_pest_when_you_control_no_pest_token(self):
        self.assertEqual(len(self.upkeep()), 1)

    def test_it_makes_none_when_you_already_control_one(self):
        self.assertEqual(len(self.upkeep(mine=[PEST])), 1)  # the one that was already there, and no second

    def test_a_pest_card_that_is_not_a_token_does_not_count(self):
        self.assertEqual(len(self.upkeep(mine=[SPAWN_CARD])), 1)

    def test_an_opponents_pest_token_does_not_count(self):
        self.assertEqual(len(self.upkeep(theirs=[PEST])), 1)


SPRINGBLOOM = Card(name="Springbloom Druid", mana_cost="{2}{G}", type_line="Creature — Elf Druid", power="1", toughness="1",
                   oracle_text="When this creature enters, you may sacrifice a land. If you do, search your library for up to two "
                               "basic land cards, put them onto the battlefield tapped, then shuffle.")


class SpringbloomDruidTests(unittest.TestCase):
    def enters(self, policy, library, lands_in_play=1):
        game, _ = table3(policy)
        a = game.seats[0]
        druid = Permanent(SPRINGBLOOM)
        a.battlefield = [druid, *lands(lands_in_play, FOREST)]
        a.library = list(library)
        fire(game, a, druid, "enters")
        return a

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(SPRINGBLOOM), [])

    def test_sacrificing_a_land_fetches_two_basics_tapped(self):
        a = self.enters(pick("Yes", "Forest"), [FOREST, PLAINS, BEAR])
        lands_now = [p for p in a.battlefield if "Land" in p.card.type_line]
        self.assertEqual(sorted((p.card.name, p.tapped) for p in lands_now), [("Forest", True), ("Plains", True)])
        self.assertEqual([c.name for c in a.graveyard], ["Forest"])  # the sacrificed land

    def test_declining_keeps_the_land_and_fetches_nothing(self):
        a = self.enters(pick("No"), [FOREST, PLAINS])
        self.assertEqual(([p.card.name for p in a.battlefield if "Land" in p.card.type_line], a.graveyard, len(a.library)),
                         (["Forest"], [], 2))

    def test_with_only_one_basic_in_the_library_it_takes_that_one(self):
        a = self.enters(pick("Yes", "Forest"), [PLAINS, BEAR])
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" in p.card.type_line), ["Plains"])

    def test_with_no_land_to_sacrifice_nothing_happens(self):
        a = self.enters(pick("Yes"), [FOREST, PLAINS], lands_in_play=0)
        self.assertEqual(([p for p in a.battlefield if "Land" in p.card.type_line], len(a.library)), ([], 2))


WITCH = Card(name="Witch of the Moors", mana_cost="{3}{B}{B}", type_line="Creature — Human Warlock", power="4", toughness="4",
             oracle_text="Deathtouch\nAt the beginning of your end step, if you gained life this turn, each opponent sacrifices a "
                         "creature of their choice and you return up to one target creature card from your graveyard to your hand.")


class WitchOfTheMoorsTests(unittest.TestCase):
    def end_step(self, gain, graveyard, policy=None):
        game, _ = table3(policy or pick("Bear"))
        a, b, c = game.seats
        witch = Permanent(WITCH)
        a.battlefield = [witch]
        b.battlefield, c.battlefield = [Permanent(BEAR)], [Permanent(OGRE)]
        a.graveyard = list(graveyard)
        if gain:
            game.change_life(a, 2)
        fire(game, a, witch, "end_step")
        return a, b, c

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(WITCH), [])

    def test_each_opponent_sacrifices_and_you_get_a_creature_card_back(self):
        a, b, c = self.end_step(True, [BEAR])
        self.assertEqual((b.battlefield, c.battlefield, [x.name for x in a.hand], a.graveyard), ([], [], ["Bear"], []))

    def test_with_no_creature_card_the_sacrifice_still_happens(self):
        a, b, c = self.end_step(True, [])
        self.assertEqual((b.battlefield, c.battlefield, a.hand), ([], [], []))

    def test_a_noncreature_card_is_not_returned(self):
        a, b, c = self.end_step(True, [FOREST])
        self.assertEqual((b.battlefield, a.hand, [x.name for x in a.graveyard]), ([], [], ["Forest"]))

    def test_nothing_happens_without_gaining_life(self):
        a, b, c = self.end_step(False, [BEAR])
        self.assertEqual((len(b.battlefield), len(c.battlefield), a.hand), (1, 1, []))
