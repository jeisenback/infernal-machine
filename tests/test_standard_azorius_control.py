"""Standard's Azorius Control deck, from its cards' real Oracle text: Captain Marvel, Earth's Protector (Power-up: once, and her mana cost
less if she entered this turn) and Petrified Hamlet (choose a land card name: its abilities are locked, and it taps for {C})."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.mana import cost_of
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, PLAINS, enter, lands, real, run_stack, table3

MARVEL = real("Captain Marvel, Earth's Protector", "{3}{W}{W}", "Legendary Creature — Human Kree Hero", "Flash\nFlying, lifelink\nPower-up "
              "— {5}{W}{W}: Put a +1/+1 counter and an indestructible counter on Captain Marvel. (Activate each power-up ability only once. "
              "Reduce the cost by her mana cost if she entered this turn.)", "5", "4", colors=("W",))
HAMLET = Card(name="Petrified Hamlet", type_line="Land", produced_mana=("C",),
              oracle_text="When this land enters, choose a land card name.\nActivated abilities of sources with the chosen name can't be "
                          "activated unless they're mana abilities.\nLands with the chosen name have \"{T}: Add {C}.\"\n{T}: Add {C}.")
PASSAGE = Card(name="Rogue's Passage", type_line="Land", produced_mana=("C",),
               oracle_text="{T}: Add {C}.\n{4}, {T}: Target creature can't be blocked this turn.")
FIELD = Card(name="Sanctuary Field", type_line="Land", oracle_text="{1}, {T}: You gain 1 life.")  # a land with no mana ability


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


class PowerUpTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3()
        self.a = self.game.seats[0]

    def test_the_cards_are_understood(self):
        for card in (MARVEL, HAMLET):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_cost_is_her_mana_cost_less_the_turn_she_entered_and_it_works_only_once(self):
        self.a.battlefield = [*lands(2, PLAINS)]
        marvel = enter(self.game, self.a, MARVEL)
        self.game._perform(self.a, offered(self.game, self.a, ACTIVATE + "Captain Marvel")[0])  # {5}{W}{W} less {3}{W}{W}: {2}
        run_stack(self.game)
        self.assertEqual(marvel.counters, {"+1/+1": 1, "indestructible": 1})
        self.assertTrue(self.game.has_keyword(marvel, "indestructible"))
        self.a.battlefield += lands(7, PLAINS)
        self.assertEqual(offered(self.game, self.a, ACTIVATE + "Captain Marvel"), [])

    def test_on_a_later_turn_she_pays_the_whole_cost(self):
        marvel = Permanent(MARVEL, entered_turn=self.game.turn - 1)
        self.a.battlefield = [marvel, *lands(6, PLAINS)]
        self.assertEqual(offered(self.game, self.a, ACTIVATE + "Captain Marvel"), [])
        self.a.battlefield += lands(1, PLAINS)
        self.assertEqual(len(offered(self.game, self.a, ACTIVATE + "Captain Marvel")), 1)

    def test_a_mana_cost_takes_its_own_colors_and_then_generic_mana(self):
        self.assertEqual(cost_of("{5}{W}{W}").minus(cost_of("{3}{W}{W}")), cost_of("{2}"))
        self.assertEqual(cost_of("{2}{W}").minus(cost_of("{U}{U}")), cost_of("{W}"))


class PetrifiedHamletTests(unittest.TestCase):
    def test_it_names_a_land_whose_other_abilities_are_locked_and_which_taps_for_colorless(self):
        asked = []

        def policy(prompt, options):
            asked.append(options)
            return options.index("Sanctuary Field") if "Sanctuary Field" in options else 0

        game, _ = table3(policy)
        a, b, _ = game.seats
        field = Permanent(FIELD)
        b.battlefield = [Permanent(BEAR), Permanent(PASSAGE), field]
        self.assertNotIn(field, [m.permanent for m in game._mana_sources(b)])
        enter(game, a, HAMLET)
        run_stack(game)
        self.assertNotIn("Bear", asked[0])  # only land card names
        self.assertIn(field, [m.permanent for m in game._mana_sources(b)])
        self.assertEqual(offered(game, b, ACTIVATE + "Sanctuary Field"), [])


if __name__ == "__main__":
    unittest.main()
