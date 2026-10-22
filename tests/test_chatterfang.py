"""Chatterfang, Squirrel General (Korvold's deck): "If one or more tokens would be created under your control, those tokens plus that many 1/1
green Squirrel creature tokens are created instead." and "{B}, Sacrifice X Squirrels: Target creature gets +X/-X until end of turn." From
the real Oracle text, with Doubling Season, Pitiless Plunderer and Academy Manufactor from theirs, and probes."""

import unittest

from infernal_machine.effects import SQUIRREL, TREASURE
from infernal_machine.game import SACRIFICE_COST_PROMPT, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, lands, names, real, run_stack, table3

CHATTERFANG = real("Chatterfang, Squirrel General", "{2}{G}", "Legendary Creature — Squirrel Warrior",
                   "Forestwalk (This creature can't be blocked as long as defending player controls a Forest.)\nIf one or more tokens would be "
                   "created under your control, those tokens plus that many 1/1 green Squirrel creature tokens are created instead.\n{B}, "
                   "Sacrifice X Squirrels: Target creature gets +X/-X until end of turn.", "3", "3", colors=("G",))
SECOND = real("Second Chatterfang", "{2}{G}", "Creature — Squirrel Warrior", CHATTERFANG.oracle_text, "3", "3", colors=("G",))  # a probe: not legendary
DOUBLING = real("Doubling Season", "{4}{G}", "Enchantment",
                "If an effect would create one or more tokens under your control, it creates twice that many of those tokens instead.\nIf an "
                "effect would put one or more counters on a permanent you control, it puts twice that many of those counters on that "
                "permanent instead.", colors=("G",))
MANUFACTOR = real("Academy Manufactor", "{3}", "Artifact Creature — Assembly-Worker",
                  "If you would create a Clue, Food, or Treasure token, instead create one of each.", "1", "3")
PLUNDERER = real("Pitiless Plunderer", "{3}{B}", "Creature — Human Pirate",
                 "Whenever another creature you control dies, create a Treasure token.", "1", "4", colors=("B",))
TREASURE_MAKER = real("Treasure Maker", "{1}", "Creature — Probe", "{T}: Create two Treasure tokens.", "1", "1")
CITIZEN = real("Citizen", "{1}", "Creature — Human", "", "1", "1")
SQUIRRELS = lambda n: [Permanent(SQUIRREL, sick=False) for _ in range(n)]  # noqa: E731


def choose_x(x):
    def policy(prompt, options):
        if X_PROMPT.matches(prompt):
            return options.index(str(x))
        want = "Squirrel" if SACRIFICE_COST_PROMPT.matches(prompt) else "Ogre"  # the tokens to sacrifice, and the target
        return next((i for i, o in enumerate(options) if o.startswith(want)), 0)
    return policy


def seat_with(*permanents, x=0):
    game, _ = table3(choose_x(x))
    a = game.seats[0]
    a.battlefield = list(permanents)
    return game, a


def made(game, seat, token, count):
    before = len(seat.battlefield)
    game.create_tokens(seat, token, count)
    return sorted(p.card.name for p in seat.battlefield[before:])


class ParseTests(unittest.TestCase):
    def test_every_line_is_read(self):
        self.assertEqual(unsupported_lines(CHATTERFANG), [])


class ReplacementTests(unittest.TestCase):
    def test_a_token_comes_with_a_squirrel(self):
        game, a = seat_with(Permanent(CHATTERFANG))
        self.assertEqual(made(game, a, TREASURE, 1), ["Squirrel", "Treasure"])

    def test_as_many_squirrels_as_tokens(self):
        game, a = seat_with(Permanent(CHATTERFANG))
        self.assertEqual(made(game, a, TREASURE, 3), ["Squirrel"] * 3 + ["Treasure"] * 3)

    def test_the_squirrels_are_ordinary_creature_tokens(self):
        game, a = seat_with(Permanent(CHATTERFANG))
        game.create_tokens(a, TREASURE, 1)
        squirrel = next(p for p in a.battlefield if p.card.name == "Squirrel")
        self.assertEqual((game.power(squirrel), game.toughness(squirrel), "Creature" in squirrel.card.type_line, squirrel.card.colors),
                         (1, 1, True, ("G",)))

    def test_squirrels_made_by_it_do_not_make_more(self):
        game, a = seat_with(Permanent(CHATTERFANG))
        self.assertEqual(made(game, a, SQUIRREL, 1), ["Squirrel", "Squirrel"])

    def test_an_opponents_tokens_are_left_alone(self):
        game, a = seat_with(Permanent(CHATTERFANG))
        self.assertEqual(made(game, game.seats[1], TREASURE, 1), ["Treasure"])

    def test_without_it_nothing_changes(self):
        game, a = seat_with()
        self.assertEqual(made(game, a, TREASURE, 2), ["Treasure"] * 2)

    def test_doubling_season_doubles_the_squirrels_too(self):
        game, a = seat_with(Permanent(CHATTERFANG), Permanent(DOUBLING))
        self.assertEqual(made(game, a, TREASURE, 1), ["Squirrel"] * 2 + ["Treasure"] * 2)

    def test_two_of_them_each_add_as_many_squirrels_to_what_the_other_left(self):
        game, a = seat_with(Permanent(CHATTERFANG), Permanent(SECOND))
        self.assertEqual(made(game, a, TREASURE, 1), ["Squirrel"] * 3 + ["Treasure"])  # the Treasure, a Squirrel, then two more

    def test_academy_manufactor_makes_its_three_and_a_squirrel_for_each(self):
        game, a = seat_with(Permanent(CHATTERFANG), Permanent(MANUFACTOR))
        self.assertEqual(made(game, a, TREASURE, 1), ["Clue", "Food", "Squirrel", "Squirrel", "Squirrel", "Treasure"])

    def test_a_creature_dying_to_pitiless_plunderer_brings_a_squirrel(self):
        game, a = seat_with(Permanent(CHATTERFANG), Permanent(PLUNDERER), Permanent(CITIZEN))
        game.destroy(a.battlefield[2])
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name in ("Squirrel", "Treasure")), ["Squirrel", "Treasure"])

    def test_one_activation_that_makes_two_tokens_makes_two_squirrels(self):
        game, a = seat_with(Permanent(CHATTERFANG), Permanent(TREASURE_MAKER, sick=False))
        action = next(x for x in game.legal_actions(a) if "Create two Treasure" in x)
        game._perform(a, action)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name in ("Squirrel", "Treasure")), ["Squirrel"] * 2 + ["Treasure"] * 2)


class SacrificeSquirrelsTests(unittest.TestCase):
    def activate(self, game, a):
        action = next(x for x in game.legal_actions(a) if "Sacrifice X Squirrels" in x)
        game._perform(a, action)
        run_stack(game)

    def board(self, squirrels, x):
        game, a = seat_with(Permanent(CHATTERFANG), *SQUIRRELS(squirrels), *lands(2), x=x)
        ogre = Permanent(OGRE)
        game.seats[1].battlefield = [ogre]
        return game, a, ogre

    def test_x_squirrels_are_sacrificed_and_the_target_gets_plus_x_minus_x(self):
        game, a, ogre = self.board(3, 2)
        self.activate(game, a)
        self.assertEqual((game.power(ogre), game.toughness(ogre)), (5, 1))
        self.assertEqual(names(a).count("Squirrel"), 1)

    def test_x_can_be_all_of_them_and_kills_the_target(self):
        game, a, ogre = self.board(3, 3)
        self.activate(game, a)
        game._check_state()
        self.assertNotIn(ogre, game.seats[1].battlefield)
        self.assertEqual(names(a).count("Squirrel"), 0)

    def test_x_is_zero_costs_only_the_mana(self):
        game, a, ogre = self.board(2, 0)
        self.activate(game, a)
        self.assertEqual((game.power(ogre), game.toughness(ogre)), (3, 3))
        self.assertEqual(names(a).count("Squirrel"), 2)
        self.assertTrue(any(p.tapped for p in a.battlefield))

    def test_x_cannot_be_more_than_the_squirrels_there_are(self):
        game, a, ogre = self.board(2, 0)
        seen = []
        original = a.player.policy
        a.player.policy = lambda prompt, options: seen.append(list(options)) or original(prompt, options) if X_PROMPT.matches(prompt) else original(prompt, options)
        self.activate(game, a)
        self.assertEqual(seen, [["0", "1", "2", "3"]])  # its two Squirrels and itself, a Squirrel Warrior

    def test_it_can_sacrifice_itself_as_a_squirrel(self):
        game, a, ogre = self.board(0, 1)
        self.activate(game, a)
        self.assertNotIn(CHATTERFANG.name, names(a))
        self.assertEqual((game.power(ogre), game.toughness(ogre)), (4, 2))

    def test_with_nothing_of_the_kind_to_sacrifice_x_is_zero_and_it_is_still_offered(self):
        goblin_maker = real("Goblin Maker", "{1}", "Creature \u2014 Probe", "{B}, Sacrifice X Goblins: Draw X cards.", "1", "1")
        game, a = seat_with(Permanent(goblin_maker), *lands(1))
        self.assertTrue([x for x in game.legal_actions(a) if "Sacrifice X Goblins" in x])

    def test_it_needs_the_mana(self):
        game, a = seat_with(Permanent(CHATTERFANG), *SQUIRRELS(2))
        self.assertFalse([x for x in game.legal_actions(a) if "Sacrifice X Squirrels" in x])


if __name__ == "__main__":
    unittest.main()
