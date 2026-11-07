"""Rolling a die (CR 706): "roll a d20" and what is "equal to the result". Lines are the cards' own Oracle text; the die is scripted."""

import unittest

from infernal_machine.combat import Attack
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, fire, pick, real, table3

COPPER = real("Ancient Copper Dragon", "{4}{R}{R}", "Creature — Elder Dragon",
              "Flying\nWhenever this creature deals combat damage to a player, roll a d20. You create a number of Treasure tokens equal to "
              "the result.", "6", "5", colors=("R",))
GOLD = real("Ancient Gold Dragon", "{5}{W}{W}", "Creature — Elder Dragon",
            "Flying\nWhenever this creature deals combat damage to a player, roll a d20. You create a number of 1/1 blue Faerie Dragon "
            "creature tokens with flying equal to the result.", "7", "10", colors=("W",))
SILVER = real("Ancient Silver Dragon", "{6}{U}{U}", "Creature — Elder Dragon",
              "Flying\nWhenever this creature deals combat damage to a player, roll a d20. Draw cards equal to the result. You have no "
              "maximum hand size for the rest of the game.", "8", "8", colors=("U",))


class Die:
    """Every roll comes out as `result` (and remembers how many sides it was asked for)."""

    def __init__(self, result: int):
        self.result, self.sides = result, None

    def randint(self, low: int, high: int) -> int:
        self.sides = high
        return self.result


def names(seat):
    return [p.card.name for p in seat.battlefield]


class DieRollTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (COPPER, GOLD, SILVER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_copper_makes_as_many_treasures_as_the_d20_shows(self):
        for result in (7, 1):
            game, _ = table3()
            game.rng = die = Die(result)
            a = game.seats[0]
            dragon = Permanent(COPPER)
            a.battlefield = [dragon]
            fire(game, a, dragon, "combat_damage_to_player")
            self.assertEqual((names(a).count("Treasure"), die.sides), (result, 20), result)

    def test_gold_makes_flying_faerie_dragons(self):
        game, _ = table3()
        game.rng = Die(3)
        a = game.seats[0]
        dragon = Permanent(GOLD)
        a.battlefield = [dragon]
        fire(game, a, dragon, "combat_damage_to_player")
        faeries = [p for p in a.battlefield if p.card.name == "Faerie Dragon"]
        self.assertEqual((len(faeries), all(game.has_keyword(p, "flying") for p in faeries)), (3, True))

    def test_silver_draws_and_keeps_its_hand_for_the_rest_of_the_game(self):
        game, _ = table3()
        game.rng = Die(12)
        a, b, _ = game.seats
        dragon = Permanent(SILVER)
        a.battlefield, a.library = [dragon], [FOREST] * 20
        fire(game, a, dragon, "combat_damage_to_player")
        a.battlefield = []  # the dragon gone: the rest of the game still
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual(len(a.hand), 12)
        b.hand = [FOREST] * 9  # an opponent still discards down to seven
        game._turn_based_actions(b)
        self.assertEqual(len(b.hand), 7)


HOARDING_OGRE = real("Hoarding Ogre", "{3}{R}", "Creature — Ogre",
                     "Whenever this creature attacks, roll a d20.\n1\u20149 | Create a Treasure token. (It's an artifact with \"{T}, Sacrifice "
                     "this token: Add one mana of any color.\")\n10\u201419 | Create two Treasure tokens.\n20 | Create three Treasure tokens.",
                     "3", "3", colors=("R",))
DELINA = real("Delina, Wild Mage", "{3}{R}", "Legendary Creature — Elf Shaman",
              "Whenever Delina attacks, choose target creature you control, then roll a d20.\n1\u201414 | Create a tapped and attacking token "
              "that's a copy of that creature, except it's not legendary and it has \"At end of combat, exile this token.\"\n15\u201420 | "
              "Create one of those tokens. You may roll again.", "3", "2", colors=("R",))
CHAMPION = real("Test Champion", "{2}{W}", "Legendary Creature — Human Knight", "", "3", "3")


COMPONENT_POUCH = real("Component Pouch", "{3}", "Artifact",
                       "{T}, Remove a component counter from this artifact: Add two mana of different colors.\n{T}: Roll a d20.\n1\u20149 | Put a "
                       "component counter on this artifact.\n10\u201420 | Put two component counters on this artifact.")


class Dice:
    """The rolls come out as listed."""

    def __init__(self, *results: int):
        self.results = list(results)

    def randint(self, low: int, high: int) -> int:
        return self.results.pop(0)


class DieTableTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (HOARDING_OGRE, DELINA):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_row_that_acts_on_the_source_is_not_read_yet(self):
        self.assertIn("{T}: Roll a d20. 1\u20149 | Put a component counter on this artifact. 10\u201420 | Put two component counters on this "
                      "artifact.", unsupported_lines(COMPONENT_POUCH))

    def test_the_row_the_result_falls_in_happens(self):
        for result, treasures in ((1, 1), (9, 1), (10, 2), (19, 2), (20, 3)):
            game, _ = table3()
            game.rng = Die(result)
            a = game.seats[0]
            ogre = Permanent(HOARDING_OGRE)
            a.battlefield = [ogre]
            fire(game, a, ogre, "attacks")
            self.assertEqual(names(a).count("Treasure"), treasures, result)

    def test_delina_copies_the_creature_and_rolls_again_on_15_or_more(self):
        for rolls, again, copies in (((16, 3), "Yes", 2), ((16,), "No", 1), ((14,), "Yes", 1)):
            target = pick("Test Champion")
            game, _ = table3(lambda prompt, options, again=again: options.index(again) if options == ["Yes", "No"] else target(prompt, options))
            game.rng = Dice(*rolls)
            a, b, _ = game.seats
            delina, champion = Permanent(DELINA), Permanent(CHAMPION)
            a.battlefield = [delina, champion]
            game.combat.attacks.append(Attack(delina, a, b))
            fire(game, a, delina, "attacks")
            made = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
            self.assertEqual(len(made), copies, rolls)
            self.assertTrue(all(p.tapped and "Legendary" not in p.card.type_line and p.card.name == "Test Champion" for p in made))
            self.assertEqual(sum(x.attacker in made and x.defender is b for x in game.combat.attacks), copies)  # attacking whom Delina attacks
            game.step = "main2"  # past the end of combat
            game._turn_based_actions(a)
            self.assertEqual([p for p in a.battlefield if p.card.type_line.startswith("Token")], [])
