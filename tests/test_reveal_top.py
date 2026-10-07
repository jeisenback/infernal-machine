import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import RevealTop, activated_abilities
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_ability_costs import MOUNTAIN, SPARE, activations, settle
from tests.test_effects import lands, pick, table

TEXT = ("{4}: Scry 1, then reveal the top card of your library. If it's a land card, put it onto the battlefield "
        "tapped. Otherwise, draw a card.")
HERO = Card(name="Hero", type_line="Legendary Creature — Merfolk", power="1", toughness="4", oracle_text=TEXT)


def setup(top):
    game, _, _ = table(pick(ACTIVATE))
    a = game.seats[0]
    a.battlefield = [Permanent(HERO)] + lands(4)
    a.library = [top, SPARE, SPARE]
    return game, a


class RevealTopTests(unittest.TestCase):
    def test_parse(self):
        (ability,) = activated_abilities(HERO)
        self.assertEqual(ability.effects, (RevealTop(1, True),))
        self.assertEqual(unsupported_lines(HERO), [])

    def test_a_land_goes_onto_the_battlefield_tapped(self):
        game, a = setup(MOUNTAIN)
        settle(game)
        entered = a.battlefield[-1]
        self.assertEqual((entered.card.name, entered.tapped, len(a.hand)), ("Mountain", True, 0))

    def test_a_nonland_is_drawn(self):
        game, a = setup(SPARE)
        settle(game)
        self.assertEqual((len(a.hand), len(a.library)), (1, 2))

    def test_a_lone_step_is_unsupported(self):
        card = Card(name="x", type_line="Creature — Bear", oracle_text="{4}: Otherwise, draw a card.")
        self.assertEqual(activated_abilities(card), ())

    def test_the_card_is_revealed_after_scrying(self):
        game, a = setup(SPARE)
        a.library = [SPARE, MOUNTAIN]  # scrying the nonland away would reveal the land next
        game.seats[0].player.choose = lambda prompt, options: 1 if "bottom" in " ".join(options).lower() else 0
        game.reveal_top_land_or_draw(a, 1, True)
        self.assertEqual(a.battlefield[-1].card.name, "Mountain")


if __name__ == "__main__":
    unittest.main()
