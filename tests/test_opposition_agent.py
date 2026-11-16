"""Opposition Agent, from its real Oracle text: "You control your opponents while they're searching their libraries." and "While an opponent
is searching their library, they exile each card they find. You may play those cards for as long as they remain exiled, and you may spend
mana as though it were mana of any color to cast them." The Agent's controller makes the opponent's search choices, and what is found is
exiled for them to play; their own searches, and an opponent's without the Agent, go as usual."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.zones import CAST_EXILE, PLAY_EXILE
from tests.helpers import BEAR, FOREST, SWAMP, lands, pick, real, table3

AGENT = real("Opposition Agent", "{2}{B}", "Creature — Human Rogue", "Flash\nYou control your opponents while they're searching their "
             "libraries.\nWhile an opponent is searching their library, they exile each card they find. You may play those cards for as long "
             "as they remain exiled, and you may spend mana as though it were mana of any color to cast them.", "3", "2", colors=("B",))
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))


def opposed(agent=True):
    """Seat 0 (with Opposition Agent, unless `agent` is False) picks Llanowar Elves; seat 1, searching, would pick the first card."""
    game, _ = table3(pick("Llanowar Elves", "Forest"))
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(AGENT)] if agent else []
    b.library = [BEAR, ELVES, FOREST]
    return game, a, b


class OppositionAgentTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(AGENT), [])

    def test_the_agents_controller_chooses_and_the_card_found_is_exiled_for_them(self):
        game, a, b = opposed()
        game.tutor(b, "creature", "hand", reveal=False)
        self.assertEqual((b.hand, a.exile, sorted(c.name for c in b.library)), ([], [ELVES], ["Bear", "Forest"]))

    def test_they_may_cast_it_with_mana_of_any_color_for_as_long_as_it_remains_exiled(self):
        game, a, b = opposed()
        a.battlefield += [Permanent(SWAMP)]
        game.tutor(b, "creature", "hand", reveal=False)
        game.turn += 5
        self.assertIn(CAST_EXILE + "Llanowar Elves", game.legal_actions(a))

    def test_a_land_found_is_exiled_and_they_may_play_it(self):
        game, a, b = opposed()
        game.fetch_basic_land(b)
        self.assertEqual(([p.card.name for p in b.battlefield], a.exile), ([], [FOREST]))
        game.active, game.step = a.index, "main1"
        self.assertIn(PLAY_EXILE + "Forest", game.legal_actions(a))

    def test_lands_searched_for_are_exiled_too(self):
        game, a, b = opposed()
        game.search_for_lands(b, 1, ("Forest",), 0, False, False)
        self.assertEqual((b.hand, a.exile), ([], [FOREST]))

    def test_a_card_found_to_be_cast_or_put_onto_the_battlefield_is_exiled_instead(self):
        for search in (lambda game, b: game.search_cast_free(b, "creature"), lambda game, b: game.search_library_or_graveyard(b, "creature"),
                       lambda game, b: game.transmute_artifact(b)):
            game, a, b = opposed()
            b.library = [real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.", None, None), ELVES]
            b.battlefield = [Permanent(real("Ornithopter", "{0}", "Artifact Creature \u2014 Thopter", "Flying", "0", "2"))]
            search(game, b)
            self.assertEqual(([p.card.name for p in b.battlefield if p.card.name != "Ornithopter"], len(a.exile), game.stack), ([], 1, []))

    def test_your_own_search_and_one_without_the_agent_go_as_usual(self):
        game, a, b = opposed()
        a.library = [BEAR, ELVES]
        game.tutor(a, "creature", "hand", reveal=False)
        self.assertEqual((a.hand, a.exile), ([ELVES], []))
        game, a, b = opposed(agent=False)
        b.battlefield += lands(1)
        game.tutor(b, "creature", "hand", reveal=False)
        self.assertEqual((b.hand, a.exile), ([BEAR], []))  # seat 1 chose for itself


if __name__ == "__main__":
    unittest.main()
