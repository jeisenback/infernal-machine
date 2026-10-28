"""Mind Swap (Superior Spider-Man, #564): enter as a copy of a creature card in a graveyard, keeping its own name, as a 4/4 Spider Human
Hero in addition, and exile that card."""

import unittest

from infernal_machine.effects import clone_rule
from infernal_machine.game import CAST, CLONE_PROMPT, NOT_A_COPY, PASS
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table

HERO = real("Test Hero", "{1}{W}", "Legendary Creature — Human Knight", "Vigilance", "2", "2")


def choosing(wanted):
    """Policy: cast the card, copy the graveyard card whose label starts with `wanted` (nothing, for None), else pass."""
    def policy(prompt, options):
        if CLONE_PROMPT.matches(prompt):
            return options.index(NOT_A_COPY) if wanted is None else next(i for i, option in enumerate(options) if option.startswith(wanted))
        return next((i for i, option in enumerate(options) if option.startswith(CAST)), options.index(PASS) if PASS in options else 0)
    return policy


def enter(card, graveyards, wanted):
    """Seat 0 casts `card` with the two graveyards as given; the clone copies `wanted`."""
    game, _, _ = table(choosing(wanted))
    a, b = game.seats
    a.hand, a.battlefield = [card], lands(6)
    a.graveyard, b.graveyard = list(graveyards[0]), list(graveyards[1])
    game._priority_round(a)
    run_stack(game)
    return game, a, b


def entered(seat, name):
    return next(p for p in seat.battlefield if p.card.name == name and p.real_card is not None)


def offered(card, graveyards):
    """The cards the clone prompt offers."""
    seen = []
    game, _, _ = table(lambda prompt, options: seen.extend(options) or choosing(None)(prompt, options))
    a, b = game.seats
    a.hand, a.battlefield = [card], lands(6)
    a.graveyard, b.graveyard = list(graveyards[0]), list(graveyards[1])
    game._priority_round(a)
    run_stack(game)
    return [label.split(" (")[0] for label in seen if label != NOT_A_COPY and not label.startswith(CAST) and label != PASS]


SPIDER_MAN = real("Superior Spider-Man", "{2}{U}{B}", "Legendary Creature — Spider Human Hero",
                  "Mind Swap — You may have Superior Spider-Man enter as a copy of any creature card in a graveyard, except his name is "
                  "Superior Spider-Man and he's a 4/4 Spider Human Hero in addition to his other types. When you do, exile that card.", "4", "4")
WALL = real("Spent Wall", "{1}{W}", "Artifact", "")


class MindSwapTests(unittest.TestCase):
    def test_the_card_is_fully_playable_and_its_rule_says_what_changes(self):
        self.assertEqual(unsupported_lines(SPIDER_MAN), [])
        rule = clone_rule(SPIDER_MAN)
        assert rule is not None
        self.assertEqual((rule.kind, rule.zone, rule.exile_copied), ("creature", "graveyard", True))
        self.assertEqual((rule.changes.name, rule.changes.power_toughness, rule.changes.add_types), ("CARDNAME", ("4", "4"), ("Spider", "Human", "Hero")))

    def test_it_enters_as_the_copy_with_its_own_name_and_the_card_is_exiled(self):
        game, a, b = enter(SPIDER_MAN, ([BEAR], [HERO]), "Test Hero")
        copy = entered(a, "Superior Spider-Man")
        self.assertEqual(copy.card.type_line, "Legendary Creature — Human Knight Spider Hero")
        self.assertEqual((copy.card.power, copy.card.toughness), ("4", "4"))
        self.assertEqual(copy.card.oracle_text, "Vigilance", "the copied card's abilities, as a copy has")
        self.assertEqual([c.name for c in b.graveyard], [], "the card it copied is exiled")
        self.assertEqual([c.name for c in b.exile], ["Test Hero"])
        self.assertEqual([c.name for c in a.graveyard], ["Bear"], "the other graveyard is untouched")

    def test_declining_leaves_it_itself_and_the_graveyards_alone(self):
        game, a, b = enter(SPIDER_MAN, ([BEAR], [HERO]), None)
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Superior Spider-Man"], ["Superior Spider-Man"])
        self.assertEqual([c.name for c in b.graveyard], ["Test Hero"])

    def test_only_creature_cards_are_offered(self):
        self.assertEqual(offered(SPIDER_MAN, ([WALL, BEAR], [])), ["Bear"])


if __name__ == "__main__":
    unittest.main()
