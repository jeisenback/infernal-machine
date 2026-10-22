import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.game import CAST, CAST_COMMANDER, PASS, Game, Permanent, _instant_speed
from tests.helpers import ScriptedPlayer

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear")
GROWTH = Card(name="Giant Growth", mana_cost="{G}", cmc=1, type_line="Instant")
DIVINATION = Card(name="Divination", mana_cost="{2}{U}", cmc=3, type_line="Sorcery")
COMMANDER = Card(name="Omnath", mana_cost="{G}", cmc=1, type_line="Legendary Creature — Elemental")


def choose(*names):
    """Policy: take the first listed action that's available, else pass."""
    def policy(prompt, options):
        for name in names:
            if name in options:
                return options.index(name)
        return options.index(PASS) if PASS in options else 0
    return policy


def table(policy_a=None, policy_b=None):
    a, b = ScriptedPlayer("A", policy_a), ScriptedPlayer("B", policy_b)
    deck = Deck(commanders=[COMMANDER], main=[FOREST] * 99, sideboard=[])
    game = Game([(a, deck), (b, deck)], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    for seat in game.seats:
        seat.hand = []
    return game, a, b


def lands(*cards):
    return [Permanent(c) for c in cards]


class CastingTests(unittest.TestCase):
    def test_cast_creature_taps_lands_and_resolves(self):
        game, a, _ = table(choose(CAST + BEAR.name))
        seat = game.seats[0]
        seat.hand = [BEAR]
        seat.battlefield = lands(FOREST, ISLAND, FOREST)
        game._priority_round(seat)
        self.assertEqual([p.card.name for p in seat.battlefield], ["Forest", "Island", "Forest", "Grizzly Bears"])
        self.assertEqual(sum(p.tapped for p in seat.battlefield), 2)
        self.assertEqual(seat.hand, [])
        self.assertEqual([e["event"] for e in a.events if e["event"] in ("cast", "resolve")], ["cast", "resolve"])

    def test_not_castable_without_the_right_mana(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [BEAR]
        seat.battlefield = lands(ISLAND, ISLAND)
        self.assertEqual(game.legal_actions(seat), [PASS])

    def test_sorcery_speed_only_for_active_player_with_empty_stack(self):
        game, _, _ = table()
        a, b = game.seats
        for seat in (a, b):
            seat.command_zone = []
            seat.hand = [DIVINATION, GROWTH]
            seat.battlefield = lands(ISLAND, ISLAND, ISLAND, FOREST)
        self.assertEqual(game.legal_actions(a), [PASS, CAST + DIVINATION.name, CAST + GROWTH.name])
        self.assertEqual(game.legal_actions(b), [PASS, CAST + GROWTH.name])
        game.step = "beginning_of_combat"
        self.assertEqual(game.legal_actions(a), [PASS, CAST + GROWTH.name])

    def test_stack_resolves_last_in_first_out(self):
        game, a, b = table(choose(CAST + BEAR.name), choose(CAST + GROWTH.name))
        game.seats[0].hand = [BEAR]
        game.seats[0].battlefield = lands(FOREST, FOREST)
        game.seats[1].hand = [GROWTH]
        game.seats[1].battlefield = lands(FOREST)
        game._priority_round(game.seats[0])
        order = [(e["event"], e["card"]) for e in a.events if e["event"] in ("cast", "resolve")]
        self.assertEqual(order, [
            ("cast", "Grizzly Bears"), ("cast", "Giant Growth"),
            ("resolve", "Giant Growth"), ("resolve", "Grizzly Bears"),
        ])
        self.assertEqual(game.seats[1].graveyard, [GROWTH])
        self.assertEqual(game.stack, [])

    def test_commander_tax(self):
        game, _, _ = table(choose(CAST_COMMANDER + COMMANDER.name))
        seat = game.seats[0]
        seat.battlefield = lands(FOREST, FOREST, FOREST)
        game._priority_round(seat)
        self.assertEqual(seat.command_zone, [])
        self.assertEqual(seat.battlefield[-1].card, COMMANDER)

        # Back to the command zone (removal isn't implemented yet): now it costs {2}{G}.
        seat.battlefield.pop()
        seat.command_zone = [COMMANDER]
        self.assertEqual(game.commander_tax(seat, COMMANDER), 2)
        self.assertNotIn(CAST_COMMANDER + COMMANDER.name, game.legal_actions(seat))  # one land left
        for permanent in seat.battlefield:
            permanent.tapped = False
        self.assertIn(CAST_COMMANDER + COMMANDER.name, game.legal_actions(seat))

    def test_untap_step(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(FOREST, tapped=True)]
        game.step = "untap"
        game._turn_based_actions(seat)
        self.assertFalse(seat.battlefield[0].tapped)

    def test_flash(self):
        self.assertTrue(_instant_speed(Card(name="x", oracle_text="Flash\nFlying")))
        self.assertTrue(_instant_speed(Card(name="x", oracle_text="Flash (You may cast this spell any time you could cast an instant.)")))
        self.assertTrue(_instant_speed(Card(name="x", oracle_text="Flying, flash")))
        self.assertFalse(_instant_speed(Card(name="x", oracle_text="When you cast a spell with flash, draw a card.")))


if __name__ == "__main__":
    unittest.main()
