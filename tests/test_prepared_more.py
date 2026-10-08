import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Condition, PrepareEach, TargetPrepared, activated_abilities, spell_effects,
                                      triggered_abilities)
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

SPELL = Card(name="Quick Study", mana_cost="{1}{U}", type_line="Instant", oracle_text="Draw two cards.", cmc=2.0)
PREPARER = Card(name="Student // Quick Study", mana_cost="{1}{U}", type_line="Creature — Wizard", oracle_text="Flying",
                prepare=SPELL)
WAYPOINT = Card(name="Skycoach Waypoint", type_line="Land",
                oracle_text="{T}: Add {C}.\n{3}, {T}: Target creature becomes prepared. (Only creatures with prepare "
                            "spells can become prepared.)")
ARENA = Card(name="Hexhaven Dueling Arena", type_line="Land",
             oracle_text="{T}: Add {C}.\n{2}, {T}: Target creature that attacked this turn becomes prepared. Activate "
                         "only as a sorcery.\n{4}, {T}: Target creature becomes prepared.")
CODIE = Card(name="Codie, Ravenous Codex", mana_cost="{3}", type_line="Legendary Artifact Creature — Book Construct",
             oracle_text="{W}{U}{B}{R}{G}, {T}: Each creature you control becomes prepared.")
SHAPER = Card(name="Paradox Shaper // Quick Study", mana_cost="{1}", type_line="Creature — Octopus Wizard",
              oracle_text="At the beginning of your upkeep, if this creature isn't prepared, it becomes prepared.",
              prepare=SPELL)
ARCHIVIST = Card(name="Archivist // Quick Study", mana_cost="{1}", type_line="Creature — Dwarf",
                 oracle_text="At the beginning of your upkeep, if there are three or more artifact and/or creature cards "
                             "in your graveyard, this creature becomes prepared.", prepare=SPELL)
LORESPINNER = Card(name="Lorespinner // Quick Study", mana_cost="{1}", type_line="Creature — Jackal",
                   oracle_text="At the beginning of your upkeep, if a player has one or fewer cards in hand, this "
                               "creature becomes prepared.", prepare=SPELL)
RESEARCHERS = Card(name="Researchers // Quick Study", mana_cost="{1}", type_line="Creature — Human",
                   oracle_text="At the beginning of each end step, if an opponent has more cards in hand than you, this "
                               "creature becomes prepared.", prepare=SPELL)
TRINKET = Card(name="Trinket", type_line="Artifact", oracle_text="")


def activate(game, seat, text):
    [action] = [a for a in game._activations(seat, True) if text in a]
    game._perform(seat, action)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(Card(name="X", type_line="Sorcery", oracle_text="Target creature becomes unprepared.")),
                         [TargetPrepared("creature", False)])
        [ability] = [a for a in activated_abilities(CODIE)]
        self.assertEqual(ability.effects, (PrepareEach(),))

    def test_conditions(self):
        conditions = {c.name: triggered_abilities(c)[0].condition for c in (SHAPER, ARCHIVIST, LORESPINNER, RESEARCHERS)}
        self.assertEqual(conditions["Paradox Shaper // Quick Study"], Condition("not_prepared"))
        self.assertEqual(conditions["Archivist // Quick Study"], Condition("graveyard_at_least", 3, "artifact or creature"))
        self.assertEqual(conditions["Lorespinner // Quick Study"], Condition("any_hand_at_most", 1))
        self.assertEqual(conditions["Researchers // Quick Study"], Condition("opponent_more_cards"))

    def test_the_report_no_longer_lists_these_lines(self):
        for card in (WAYPOINT, ARENA, CODIE, SHAPER, ARCHIVIST, LORESPINNER, RESEARCHERS):
            self.assertEqual(unsupported_lines(card), [], card.name)


class PrepareOthersTests(unittest.TestCase):
    def test_waypoint_prepares_the_target(self):
        game, _ = table3()
        a = game.seats[0]
        student = Permanent(PREPARER)
        a.battlefield = [Permanent(WAYPOINT), *lands(3), student]
        activate(game, a, "becomes prepared")
        self.assertTrue(student.prepared)

    def test_a_creature_without_a_prepare_spell_stays_unprepared(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(WAYPOINT), *lands(3), bear]
        activate(game, a, "becomes prepared")
        self.assertFalse(bear.prepared)

    def test_arena_only_targets_creatures_that_attacked(self):
        game, _ = table3()
        a = game.seats[0]
        attacker, idle = Permanent(PREPARER), Permanent(PREPARER)
        attacker.attacked_turn = game.turn
        a.battlefield = [Permanent(ARENA), *lands(2), attacker, idle]
        options = [option for _, option in game.target_options("creature that attacked this turn", a)]
        self.assertEqual(options, [attacker])
        self.assertEqual(len(game.target_options("creature", a)), 2)

    def test_codie_prepares_every_creature_you_control(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine, also, theirs = Permanent(PREPARER), Permanent(PREPARER), Permanent(PREPARER)
        a.battlefield = [mine, also, Permanent(BEAR)]
        b.battlefield = [theirs]
        PrepareEach().resolve(game, a, None)
        self.assertEqual((mine.prepared, also.prepared, theirs.prepared), (True, True, False))

    def test_unprepare(self):
        game, _ = table3()
        student = Permanent(PREPARER, prepared=True)
        game.seats[0].battlefield = [student]
        TargetPrepared("creature", False).resolve(game, game.seats[0], student)
        self.assertFalse(student.prepared)


class ConditionTests(unittest.TestCase):
    def upkeep(self, card, setup=None, event="upkeep"):
        game, _ = table3()
        a = game.seats[0]
        creature = Permanent(card)
        a.battlefield = [creature]
        if setup:
            setup(game, a)
        game.trigger(event, creature, a)
        run_stack(game)
        return creature

    def test_only_if_it_is_not_prepared(self):
        self.assertTrue(self.upkeep(SHAPER).prepared)
        game, _ = table3()
        a = game.seats[0]
        creature = Permanent(SHAPER, prepared=True)
        a.battlefield = [creature]
        game.trigger("upkeep", creature, a)
        game._put_triggers_on_stack()
        self.assertEqual(game.stack, [])  # the condition is false, so nothing triggers

    def test_graveyard_count(self):
        def graveyard(n):
            return lambda game, a: setattr(a, "graveyard", [BEAR] * 2 + [TRINKET] * (n - 2) if n >= 2 else [BEAR] * n)
        self.assertFalse(self.upkeep(ARCHIVIST, graveyard(2)).prepared)
        self.assertTrue(self.upkeep(ARCHIVIST, graveyard(3)).prepared)  # two creatures and an artifact

    def test_a_player_with_one_or_fewer_cards_in_hand(self):
        def hands(sizes):
            def setup(game, a):
                for seat, size in zip(game.seats, sizes):
                    seat.hand = [BEAR] * size
            return setup
        self.assertFalse(self.upkeep(LORESPINNER, hands([3, 2, 4])).prepared)
        self.assertTrue(self.upkeep(LORESPINNER, hands([3, 1, 4])).prepared)

    def test_an_opponent_has_more_cards_in_hand(self):
        def hands(sizes):
            def setup(game, a):
                for seat, size in zip(game.seats, sizes):
                    seat.hand = [BEAR] * size
            return setup
        self.assertFalse(self.upkeep(RESEARCHERS, hands([3, 3, 2]), "each_end_step").prepared)
        self.assertTrue(self.upkeep(RESEARCHERS, hands([3, 4, 2]), "each_end_step").prepared)


if __name__ == "__main__":
    unittest.main()
