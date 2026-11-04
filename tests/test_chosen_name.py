""""As this artifact enters, choose a card name." with "Activated abilities of sources with the chosen name can't be activated unless they're
mana abilities." (Pithing Needle) and "Spells with the chosen name cost {3} more to cast." (Disruptor Flute)."""

import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, ACTIVATE_GRAVEYARD, CHOOSE_NAME_PROMPT, CYCLE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, enter, lands, real, table3

NEEDLE = real("Pithing Needle", "{1}", "Artifact", "As this artifact enters, choose a card name.\nActivated abilities of sources with the "
              "chosen name can't be activated unless they're mana abilities.")
FLUTE = real("Disruptor Flute", "{2}", "Artifact", "Flash\nAs this artifact enters, choose a card name.\nSpells with the chosen name cost {3} "
             "more to cast.\nActivated abilities of sources with the chosen name can't be activated unless they're mana abilities.")
FACTORY = real("Mishra's Factory", "", "Land", "{T}: Add {C}.\n{1}: This land becomes a 2/2 Assembly-Worker artifact creature until end "
               "of turn. It's still a land.\n{T}: Target Assembly-Worker creature gets +1/+1 until end of turn.")
DELTA = real("Polluted Delta", "", "Land", "{T}, Pay 1 life, Sacrifice this land: Search your library for an Island or Swamp card, put it "
             "onto the battlefield, then shuffle.")
SANDBAR = real("Lonely Sandbar", "", "Land", "This land enters tapped.\n{T}: Add {U}.\nCycling {U} ({U}, Discard this card: Draw a card.)")
MIND_STONE = dataclasses.replace(real("Mind Stone", "{2}", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card."),
                                 produced_mana=("C",))
GHOUL = real("Blessed Ghoul", "{W/B}", "Creature — Zombie Cleric", "Lifelink\n{2}{W/B}: Return this card from your graveyard to your hand.",
             "1", "1")
ONE = Card(name="One", mana_cost="{1}", cmc=1.0, type_line="Artifact")


def naming(name, artifact=NEEDLE, graveyard=()):
    """Seat 1 holds a Factory, a Delta and a land for any color, a Sandbar in hand (and one in the graveyard, so it is in view); seat 0's artifact
    enters naming `name`."""
    def policy(prompt, options):
        return options.index(name) if CHOOSE_NAME_PROMPT.matches(prompt) else 0
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    b.battlefield, b.hand, b.library, b.graveyard = [Permanent(FACTORY), Permanent(DELTA)] + lands(1), [SANDBAR], [FOREST] * 3, [SANDBAR, *graveyard]
    a.battlefield = []
    chooser = enter(game, a, artifact)
    game.active, game.step = 1, "main1"
    return game, b, chooser


def activations(game, seat, card):
    return [action for action in game.legal_actions(seat) if action.startswith(ACTIVATE) and card.name in action]


class ChosenNameTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        self.assertEqual([unsupported_lines(NEEDLE), unsupported_lines(FLUTE)], [[], []])

    def test_the_named_cards_abilities_cannot_be_activated(self):
        game, b, needle = naming("Polluted Delta")
        self.assertEqual(needle.chosen_name, "Polluted Delta")
        self.assertEqual(activations(game, b, DELTA), [])
        self.assertNotEqual(activations(game, b, FACTORY), [])  # another name is not stopped

    def test_its_mana_ability_still_works(self):
        game, b, _ = naming("Mind Stone", graveyard=[MIND_STONE])
        b.battlefield = [Permanent(MIND_STONE)]
        self.assertEqual(activations(game, b, MIND_STONE), [])  # no sacrificing it to draw
        self.assertIsNotNone(game._payment(b, ONE))  # but it still taps for {C}

    def test_cycling_a_named_card_is_stopped(self):
        game, b, _ = naming("Lonely Sandbar")
        self.assertNotIn(CYCLE + "Lonely Sandbar", game.legal_actions(b))
        game, b, _ = naming("Polluted Delta")
        self.assertIn(CYCLE + "Lonely Sandbar", game.legal_actions(b))

    def test_an_ability_from_the_graveyard_is_stopped(self):
        game, b, _ = naming("Blessed Ghoul", graveyard=[GHOUL])
        b.battlefield += lands(2)
        self.assertNotIn(ACTIVATE_GRAVEYARD + "Blessed Ghoul", game.legal_actions(b))
        game, b, _ = naming("Polluted Delta", graveyard=[GHOUL])
        b.battlefield += lands(2)  # {2}{W/B}
        self.assertIn(ACTIVATE_GRAVEYARD + "Blessed Ghoul", game.legal_actions(b))

    def test_the_bot_names_an_opponents_permanent_with_an_activated_ability(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        b.battlefield, a.battlefield = [Permanent(FOREST), Permanent(DELTA)], []
        self.assertEqual(enter(game, a, NEEDLE).chosen_name, "Polluted Delta")

    def test_with_no_card_in_view_no_name_is_chosen(self):
        game, _ = table3()
        for seat in game.seats:
            seat.battlefield, seat.graveyard, seat.exile, seat.command_zone = [], [], [], []
        self.assertIsNone(enter(game, game.seats[0], NEEDLE).chosen_name)

    def test_the_flute_taxes_spells_with_the_chosen_name(self):
        game, b, _ = naming("Bear", FLUTE, graveyard=[BEAR])
        self.assertEqual((game.caster.cost_increase(b, BEAR), game.caster.cost_increase(b, OGRE)), (3, 0))


if __name__ == "__main__":
    unittest.main()
