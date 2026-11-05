"""Karn, the Great Creator: "Activated abilities of artifacts your opponents control can't be activated.", "+1: Until your next turn, up
to one target noncreature artifact becomes an artifact creature with power and toughness each equal to its mana value." and "−2: You may
reveal an artifact card you own from outside the game or choose a face-up artifact card you own in exile. Put that card into your
hand." """

import unittest

from infernal_machine.game import ACTIVATE, WISH_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, end_turn, lands, pick, real, run_stack, table3

KARN = real("Karn, the Great Creator", "{4}", "Legendary Planeswalker — Karn", "Activated abilities of artifacts your opponents control "
            "can't be activated.\n+1: Until your next turn, up to one target noncreature artifact becomes an artifact creature with power "
            "and toughness each equal to its mana value.\n−2: You may reveal an artifact card you own from outside the game or choose a "
            "face-up artifact card you own in exile. Put that card into your hand.")
CRYSTAL_BALL = real("Crystal Ball", "{3}", "Artifact", "{1}, {T}: Scry 2. (Look at the top two cards of your library, then put any number "
                    "of them on the bottom and the rest on top in any order.)")
LATTICE = real("Mycosynth Lattice", "{6}", "Artifact", "All permanents are artifacts in addition to their other types.\nAll cards that "
               "aren't on the battlefield, spells, and permanents are colorless.\nPlayers may spend mana as though it were mana of any color.")
SCORN_EFFIGY = real("Scorn Effigy", "{3}", "Artifact Creature — Scarecrow", "Foretell {0} (During your turn, you may pay {2} and exile "
                    "this card from your hand face down. Cast it on a later turn for its foretell cost.)", "2", "3")
ORNITHOPTER = real("Ornithopter", "{0}", "Artifact Creature — Thopter", "Flying", "0", "2")


def table(policy=None, karn=True):
    game, _ = table3(policy) if policy else table3()
    a, b, _ = game.seats
    a.battlefield = ([Permanent(KARN, loyalty=5)] if karn else []) + lands(4)
    b.battlefield = lands(4)
    a.library = b.library = [FOREST] * 5
    return game, a, b


def activate(game, seat, loyalty):
    game._perform(seat, next(x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + "Karn") and f"{loyalty}:" in x))
    run_stack(game)


def ball_activations(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + "Crystal Ball")]


class KarnTheGreatCreatorTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(KARN), [])

    def test_opponents_cannot_activate_their_artifacts_abilities_but_you_can(self):
        game, a, b = table()
        a.battlefield.append(Permanent(CRYSTAL_BALL))
        b.battlefield.append(Permanent(CRYSTAL_BALL))
        game.active = 1
        self.assertEqual(ball_activations(game, b), [])
        self.assertNotEqual(ball_activations(game, a), [])
        game, _, b = table(karn=False)
        b.battlefield.append(Permanent(CRYSTAL_BALL))
        game.active = 1
        self.assertNotEqual(ball_activations(game, b), [])

    def test_plus_one_animates_a_noncreature_artifact_until_your_next_turn(self):
        game, a, b = table(policy=pick("Crystal Ball"))
        ball = Permanent(CRYSTAL_BALL)
        b.battlefield.append(ball)
        activate(game, a, "+1")
        self.assertEqual((ball.card.type_line, game.power(ball), game.toughness(ball)), ("Artifact Creature", 3, 3))
        end_turn(game, a)
        game.active, game.step = 1, "untap"
        game._turn_based_actions(b)  # the opponent's turn: still a creature
        self.assertIn("Creature", ball.card.type_line)
        end_turn(game, b)
        game.active, game.step = 0, "untap"
        game._turn_based_actions(a)  # Karn's controller's next turn: an artifact again
        self.assertEqual(ball.card.type_line, "Artifact")

    def test_an_artifact_creature_is_not_a_target(self):
        game, a, b = table(policy=pick("Ornithopter"))
        thopter = Permanent(ORNITHOPTER)
        b.battlefield.append(thopter)
        activate(game, a, "+1")
        self.assertEqual((game.power(thopter), thopter.original), (0, None))

    def test_minus_two_puts_an_artifact_from_outside_the_game_into_your_hand(self):
        game, a, _ = table(policy=pick("Bear", "Mycosynth Lattice"))  # a creature card is not offered
        a.sideboard, a.hand = [BEAR, LATTICE], []
        activate(game, a, "−2")
        self.assertEqual((a.hand, a.sideboard), ([LATTICE], [BEAR]))

    def test_minus_two_takes_a_face_up_artifact_from_exile_but_not_a_foretold_one(self):
        game, a, _ = table(policy=pick("Forest", "Scorn Effigy", "Crystal Ball"))
        a.exile, a.foretold, a.hand = [FOREST, SCORN_EFFIGY, CRYSTAL_BALL], [(1, SCORN_EFFIGY)], []
        activate(game, a, "−2")
        self.assertEqual((a.hand, a.exile), ([CRYSTAL_BALL], [FOREST, SCORN_EFFIGY]))

    def test_minus_two_may_take_nothing(self):
        game, a, _ = table(policy=pick("Nothing"))
        a.sideboard, a.hand = [LATTICE], []
        activate(game, a, "−2")
        self.assertEqual((a.hand, a.sideboard), ([], [LATTICE]))

    def test_minus_two_asks_nothing_when_there_is_no_artifact_to_take(self):
        asked = []
        game, a, _ = table(policy=lambda prompt, options: asked.append(prompt) or (options.index("Pass") if "Pass" in options else 0))
        a.sideboard, a.exile = [BEAR], [FOREST]
        activate(game, a, "−2")
        self.assertFalse(any(WISH_PROMPT.matches(p) for p in asked))


if __name__ == "__main__":
    unittest.main()
