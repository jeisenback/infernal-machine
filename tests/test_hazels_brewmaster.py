"""Hazel's Brewmaster, from its real Oracle text: "Whenever this creature enters or attacks, exile up to one target card from a graveyard and
create a Food token." and "Foods you control have all activated abilities of all creature cards exiled with this creature." A noncreature
card exiled with it gives nothing, an opponent's Food gets nothing, and once the Brewmaster is gone its Foods are only Foods."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import enter, lands, pick, real, run_stack, table3

BREWMASTER = real("Hazel's Brewmaster", "{3}{B}", "Creature — Squirrel Warlock", "Menace\nWhenever this creature enters or attacks, "
                  "exile up to one target card from a graveyard and create a Food token.\nFoods you control have all activated abilities "
                  "of all creature cards exiled with this creature.", "3", "4", colors=("B",))
GNOMES = real("Bottle Gnomes", "{3}", "Artifact Creature — Gnome", "Sacrifice this creature: You gain 3 life.", "1", "3")
MIND_STONE = real("Mind Stone", "{2}", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.", None, None)
GAIN = "Sacrifice this creature: You gain 3 life."


def entered(graveyard, policy=None):
    """Seat 1's graveyard holds `graveyard`; Hazel's Brewmaster enters for seat 0 and its trigger resolves."""
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    b.graveyard = list(graveyard)
    brewmaster = enter(game, a, BREWMASTER)
    run_stack(game)
    return game, a, b, brewmaster


def food_abilities(game, seat):
    return [text for text, (permanent, _) in game._activations(seat, True).items() if permanent.card.name == "Food"]


class HazelsBrewmasterTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(BREWMASTER), [])

    def test_entering_exiles_a_card_and_makes_a_food_that_has_its_abilities(self):
        game, a, b, brewmaster = entered([GNOMES])
        self.assertEqual((b.graveyard, b.exile, [c for _, c in brewmaster.exiled_with]), ([], [GNOMES], [GNOMES]))
        (action,) = [x for x in food_abilities(game, a) if x.endswith(GAIN)]
        life = a.life
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((a.life - life, [p.card.name for p in a.battlefield]), (3, ["Hazel's Brewmaster"]))  # the Food was sacrificed

    def test_with_no_target_it_still_makes_a_food(self):
        game, a, b, _ = entered([GNOMES], pick("No target"))
        self.assertEqual((b.graveyard, sorted(p.card.name for p in a.battlefield)), ([GNOMES], ["Food", "Hazel's Brewmaster"]))
        self.assertFalse(any(x.endswith(GAIN) for x in food_abilities(game, a)))

    def test_a_noncreature_card_gives_nothing(self):
        game, a, b, _ = entered([MIND_STONE])
        a.battlefield += lands(1)  # the {1} could be paid
        self.assertEqual(b.exile, [MIND_STONE])
        self.assertFalse(any(x.endswith("Draw a card.") for x in food_abilities(game, a)))

    def test_only_foods_and_only_while_the_card_is_still_exiled(self):
        game, a, b, _ = entered([GNOMES])
        self.assertFalse(any(x.endswith(GAIN) and "Brewmaster" in x for x in game._activations(a, True)))
        b.exile.remove(GNOMES)
        b.graveyard.append(GNOMES)
        self.assertFalse(any(x.endswith(GAIN) for x in food_abilities(game, a)))

    def test_an_opponents_food_and_a_food_without_the_brewmaster_get_nothing(self):
        game, a, b, brewmaster = entered([GNOMES])
        b.battlefield.append(Permanent(next(p.card for p in a.battlefield if p.card.name == "Food")))
        self.assertFalse(any(x.endswith(GAIN) for x in food_abilities(game, b)))
        game.destroy(brewmaster)
        self.assertFalse(any(x.endswith(GAIN) for x in food_abilities(game, a)))


if __name__ == "__main__":
    unittest.main()
