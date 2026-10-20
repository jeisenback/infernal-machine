import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (AlternativeCost, DestroyAll, ReturnAllToHand, alternative_costs, overloaded_effects,
                                      spell_effects)
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, table3
from tests.real import REAL

PLAIN_LAND = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))

def resolve_everything(game):
    """Resolve the stack, and the abilities that trigger while it does."""
    game._put_triggers_on_stack()
    while game.stack:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()


def draw_deck(n=6):
    return [Card(name=f"Card {i}", type_line="Creature — Bear", power="1", toughness="1") for i in range(n)]


class ParseTests(unittest.TestCase):
    def test_evoke(self):
        self.assertEqual(alternative_costs(REAL["Mulldrifter"]),
                         [AlternativeCost("Evoke {2}{U}", mana_cost="{2}{U}", evoke=True)])
        self.assertEqual(unsupported_lines(REAL["Mulldrifter"]), [])

    def test_overload(self):
        [way] = alternative_costs(REAL["Cyclonic Rift"])
        self.assertEqual((way.text, way.mana_cost, way.overload), ("Overload {6}{U}", "{6}{U}", True))
        self.assertEqual(overloaded_effects(REAL["Cyclonic Rift"]),
                         [ReturnAllToHand("nonland permanent you don't control")])
        self.assertEqual(overloaded_effects(REAL["Vandalblast"]), [DestroyAll("artifact you don't control")])
        # the normal spell is unchanged
        self.assertNotEqual(spell_effects(REAL["Cyclonic Rift"]), overloaded_effects(REAL["Cyclonic Rift"]))

    def test_an_overload_that_is_not_understood_is_reported_and_not_offered(self):
        card = Card(name="Hush", mana_cost="{1}{U}", type_line="Sorcery",
                    oracle_text="Target creature can't block this turn.\nOverload {3}{U}")
        self.assertIsNone(overloaded_effects(card))  # "Each creature can't block" has no template
        self.assertEqual(alternative_costs(card), [])

    def test_cards_without_it(self):
        self.assertIsNone(overloaded_effects(REAL["Brainstorm"]))
        self.assertEqual(alternative_costs(REAL["Brainstorm"]), [])


class EvokeTests(unittest.TestCase):
    def cast(self, choice, lands_count):
        game, _ = table3(pick(choice))
        a = game.seats[0]
        a.library = draw_deck()
        a.hand = [REAL["Mulldrifter"]]
        a.battlefield = lands(lands_count)
        game._perform(a, CAST + "Mulldrifter")
        resolve_everything(game)
        return game, a

    def test_evoked_it_draws_and_is_sacrificed(self):
        game, a = self.cast("Evoke", 3)
        self.assertEqual(len(a.hand), 2)  # its "when it enters" ability still resolved
        self.assertEqual([c.name for c in a.graveyard], ["Mulldrifter"])
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Mulldrifter"], [])

    def test_cast_normally_it_stays(self):
        game, a = self.cast("Pay", 5)
        self.assertEqual(len(a.hand), 2)
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Mulldrifter"], ["Mulldrifter"])
        self.assertEqual(a.graveyard, [])

    def test_the_cheaper_way_makes_it_castable(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [REAL["Mulldrifter"]]
        a.battlefield = lands(3)
        self.assertIn(CAST + "Mulldrifter", game.legal_actions(a))
        a.battlefield = lands(2)
        self.assertNotIn(CAST + "Mulldrifter", game.legal_actions(a))


class OverloadTests(unittest.TestCase):
    def board(self, choice):
        game, _ = table3(pick(choice))
        a, b, c = game.seats
        a.hand = [REAL["Cyclonic Rift"]]
        mine = Permanent(BEAR)
        a.battlefield = [*lands(7), mine]
        theirs = [Permanent(BEAR), Permanent(BEAR)]
        b.battlefield = [*theirs, Permanent(PLAIN_LAND)]
        c.battlefield = [Permanent(BEAR)]
        return game, a, b, c, mine

    def test_overloaded_it_returns_every_nonland_permanent_you_do_not_control(self):
        game, a, b, c, mine = self.board("Overload")
        game._perform(a, CAST + "Cyclonic Rift")
        resolve_everything(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Wastes"])
        self.assertEqual(c.battlefield, [])
        self.assertEqual([x.name for x in b.hand], ["Bear", "Bear"])
        self.assertIn(mine, a.battlefield)  # yours stay
        self.assertEqual([x.name for x in a.graveyard], ["Cyclonic Rift"])

    def test_cast_normally_it_returns_one_target(self):
        game, a, b, c, mine = self.board("Pay")
        game._perform(a, CAST + "Cyclonic Rift")
        resolve_everything(game)
        self.assertEqual(len(b.battlefield) + len(c.battlefield), 3)  # four permanents they had, one bounced
        self.assertEqual(len(b.hand) + len(c.hand), 1)

    def test_overload_needs_the_full_cost(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [REAL["Cyclonic Rift"]]
        a.battlefield = [*lands(6), Permanent(BEAR)]
        a.battlefield  # six lands pay {1}{U}, so it is castable, just not overloaded
        self.assertEqual(len(game._cast_ways(a, REAL["Cyclonic Rift"], False)), 1)
        a.battlefield = [*lands(7), Permanent(BEAR)]
        self.assertEqual(len(game._cast_ways(a, REAL["Cyclonic Rift"], False)), 2)


if __name__ == "__main__":
    unittest.main()
