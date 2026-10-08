import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (MOVE_COUNTERS_PROMPT, Animate, MoveCountersFrom, PumpX, activated_abilities,
                                      spell_effects)
from infernal_machine.game import ACTIVATE, CAST, PASS, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3

SHIFT = REAL["Bioshift"]
SHIFT_ALL = Card(name="Shift All", mana_cost="{U}", type_line="Instant",
                 oracle_text="Move all +1/+1 counters from target creature onto another target creature.")
SCALE = REAL["Might of the Masses"]
TREETOP = REAL["Treetop Village"]
NEXUS = REAL["Blinkmoth Nexus"]
MUTAVAULT = REAL["Mutavault"]
AWAKEN = REAL["Llanowar Loamspeaker"]
def targets(*indexes, move=0):
    """Cast the first spell, answering each target prompt with the next index and "move how many" with `move`."""
    wanted = iter(indexes)
    base = pick(CAST)
    return lambda prompt, options: (next(wanted, 0) if prompt.startswith(TARGET_PROMPT)
                                    else move if prompt.startswith(MOVE_COUNTERS_PROMPT) else base(prompt, options))


class ScaledPumpTests(unittest.TestCase):
    def test_parse(self):
        [_, pump] = spell_effects(SCALE)
        self.assertEqual((pump.power, pump.toughness), (1, 1))
        self.assertIsInstance(pump, PumpX)

    def test_it_scales_with_the_creatures_you_control(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.hand, a.battlefield = [SCALE], lands(1) + [bear, Permanent(BEAR), Permanent(BEAR)]
        game._priority_round(a)
        self.assertEqual((game.power(bear), game.toughness(bear)), (2 + 3, 2 + 3))


class MoveCountersTests(unittest.TestCase):
    def setup(self, card, source_counters, target_counters=None, move=1):
        game, _ = table3(targets(0, 0, move=move))
        a = game.seats[0]
        source, destination = Permanent(BEAR, counters=dict(source_counters)), Permanent(OGRE, counters=dict(target_counters or {}))
        a.hand, a.battlefield = [card], lands(1) + [source, destination]
        game._priority_round(a)
        return source, destination

    def test_parse(self):
        [first, second] = spell_effects(SHIFT)
        self.assertEqual((first, second.count, second.counter, second.same_controller),
                         (MoveCountersFrom("creature"), "any", "+1/+1", True))
        self.assertEqual(spell_effects(SHIFT_ALL)[1].count, None)
        self.assertEqual(unsupported_lines(SHIFT), [])

    def test_one_counter_moves(self):
        source, destination = self.setup(SHIFT, {"+1/+1": 3})
        self.assertEqual((source.counters, destination.counters), ({"+1/+1": 2}, {"+1/+1": 1}))

    def test_all_counters_move_and_add_to_what_is_there(self):
        source, destination = self.setup(SHIFT_ALL, {"+1/+1": 3}, {"+1/+1": 2})
        self.assertEqual((source.counters, destination.counters), ({}, {"+1/+1": 5}))

    def test_nothing_to_move(self):
        source, destination = self.setup(SHIFT, {})
        self.assertEqual((source.counters, destination.counters), ({}, {}))

    def test_it_needs_a_second_creature(self):
        game, _ = table3(targets(0, 0))
        a = game.seats[0]
        only = Permanent(BEAR, counters={"+1/+1": 2})
        a.hand, a.battlefield = [SHIFT], lands(1) + [only]
        game._priority_round(a)
        self.assertEqual((only.counters, a.hand), ({"+1/+1": 2}, [SHIFT]))  # the same creature can't be both targets


class AnimateTests(unittest.TestCase):
    def test_the_lands_are_understood(self):
        for card in (TREETOP, NEXUS, MUTAVAULT):
            self.assertEqual(unsupported_lines(card), [], card.name)
        [ability] = [a for a in activated_abilities(TREETOP) if isinstance(a.effects[0], Animate)]
        self.assertEqual(ability.effects[0].colors, ("G",))

    def test_a_lone_still_a_land_is_not_understood(self):
        self.assertIsNone(spell_effects(Card(name="x", mana_cost="{G}", type_line="Instant", oracle_text="It's still a land.")))

    def activate(self, card, mana=2, turn_sick=False):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith(ACTIVATE)
                                                       and "becomes" in o), options.index(PASS) if PASS in options else 0))
        a = game.seats[0]
        land = Permanent(card)
        a.battlefield = lands(mana) + [land]  # the land itself is last, so it is not what pays for its own ability
        game._priority_round(a)
        return game, a, land

    def test_it_becomes_a_creature_with_its_keywords(self):
        game, a, land = self.activate(TREETOP, 2)
        self.assertEqual((land.card.type_line, game.power(land), game.toughness(land)),
                         ("Land Creature — Ape", 3, 3))
        self.assertTrue(game.has_keyword(land, "trample"))
        self.assertEqual(land.card.colors, ("G",))

    def test_an_artifact_creature_land_with_all_creature_types(self):
        game, a, land = self.activate(NEXUS)
        self.assertEqual(land.card.type_line, "Land Artifact Creature — Blinkmoth")
        game, a, land = self.activate(MUTAVAULT)
        self.assertEqual((land.card.type_line, land.card.colors), ("Land Creature", ()))

    def test_it_is_a_land_again_at_end_of_turn(self):
        game, a, land = self.activate(TREETOP, 2)
        game.step = "end"
        game._turn_based_actions(a)  # not yet: end of turn is cleanup
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual((land.card.type_line, land.card.power, land.until_end_of_turn), ("Land", None, []))

    def test_a_land_that_just_came_in_cannot_attack(self):
        game, a, land = self.activate(TREETOP, 2)
        self.assertTrue(game.combat._can_attack(land))  # it has been there since the turn began
        land.sick = True
        self.assertFalse(game.combat._can_attack(land))

    def test_playing_a_land_makes_it_summoning_sick(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [TREETOP]
        game._perform(a, "Play land: Treetop Village")
        self.assertTrue(a.battlefield[0].sick)

    def test_targeted(self):
        self.assertEqual(unsupported_lines(AWAKEN), [])
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith(ACTIVATE)
                                                       and "becomes" in o), options.index(PASS) if PASS in options else 0))
        a = game.seats[0]
        land = Permanent(Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",)))
        a.battlefield = [Permanent(AWAKEN), land]
        game._priority_round(a)
        self.assertEqual((land.card.type_line, game.power(land), game.has_keyword(land, "haste")),
                         ("Basic Land Creature — Elemental", 3, True))
