"""Blitz (CR 702.152): cast for its blitz cost, the creature has haste and "When this creature dies, draw a card.", and is sacrificed as
the next end step begins. Jaxis, the Troublemaker gives its copy the same. Lines are the cards' own Oracle text."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, activate, lands, pick, real, run_stack, script, table3

REQUISITIONER = real("Riveteers Requisitioner", "{1}{R}", "Creature — Lizard Rogue",
                     "When this creature dies, create a Treasure token. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of "
                     "any color.\")\nBlitz {2}{R} (If you cast this spell for its blitz cost, it gains haste and \"When this creature dies, "
                     "draw a card.\" Sacrifice it at the beginning of the next end step.)", "3", "1", colors=("R",))
MAYHEM_PATROL = real("Mayhem Patrol", "{1}{R}", "Creature — Devil Warrior",
                     "Menace (This creature can't be blocked except by two or more creatures.)\nWhenever this creature attacks, target "
                     "creature gets +1/+0 until end of turn.\nBlitz {1}{R} (If you cast this spell for its blitz cost, it gains haste and "
                     "\"When this creature dies, draw a card.\" Sacrifice it at the beginning of the next end step.)", "1", "2", colors=("R",))
NIGHT_CLUBBER = real("Night Clubber", "{1}{B}{B}", "Creature — Human Warrior",
                     "When this creature enters, creatures your opponents control get -1/-1 until end of turn.\nBlitz {2}{B} (If you cast "
                     "this spell for its blitz cost, it gains haste and \"When this creature dies, draw a card.\" Sacrifice it at the "
                     "beginning of the next end step.)", "2", "2", colors=("B",))
WORKSHOP_WARCHIEF = real("Workshop Warchief", "{3}{G}{G}", "Creature — Rhino Warrior",
                         "Trample\nWhen this creature enters, you gain 3 life.\nWhen this creature dies, create a 4/4 green Rhino Warrior "
                         "creature token.\nBlitz {4}{G}{G} (If you cast this spell for its blitz cost, it gains haste and \"When this "
                         "creature dies, draw a card.\" Sacrifice it at the beginning of the next end step.)", "5", "3", colors=("G",))
JAXIS = real("Jaxis, the Troublemaker", "{3}{R}", "Legendary Creature — Human Warrior",
             "{R}, {T}, Discard a card: Create a token that's a copy of another target creature you control. It gains haste and \"When "
             "this token dies, draw a card.\" Sacrifice it at the beginning of the next end step. Activate only as a sorcery.\nBlitz {1}{R} "
             "(If you cast this spell for its blitz cost, it gains haste and \"When this creature dies, draw a card.\" Sacrifice it at the "
             "beginning of the next end step.)", "2", "3", colors=("R",))


def end_step(game, seat):
    game.step = "end"
    game._turn_based_actions(seat)
    run_stack(game)


def creatures(seat):
    return [p for p in seat.battlefield if "Creature" in p.card.type_line]


class BlitzTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (REQUISITIONER, MAYHEM_PATROL, NIGHT_CLUBBER, WORKSHOP_WARCHIEF, JAXIS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_blitzed_it_has_haste_and_is_sacrificed_drawing_a_card(self):
        game, _ = table3(script("Blitz"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(3), [REQUISITIONER], [FOREST] * 5
        game._perform(a, CAST + "Riveteers Requisitioner")
        run_stack(game)
        [creature] = creatures(a)
        self.assertEqual((sum(p.tapped for p in a.battlefield), game.has_keyword(creature, "haste")), (3, True))
        end_step(game, a)
        self.assertEqual((creatures(a), [c.name for c in a.hand], [p.card.name for p in a.battlefield if "Treasure" in p.card.name]),
                         ([], ["Forest"], ["Treasure"]))  # its own death trigger too

    def test_cast_normally_it_stays_without_haste(self):
        game, _ = table3(script("Pay"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(2), [REQUISITIONER], [FOREST] * 5
        game._perform(a, CAST + "Riveteers Requisitioner")
        run_stack(game)
        [creature] = creatures(a)
        self.assertFalse(game.has_keyword(creature, "haste"))
        end_step(game, a)
        self.assertEqual((len(creatures(a)), a.hand), (1, []))

    def test_jaxis_copy_has_haste_and_draws_when_it_dies(self):
        game, _ = table3(pick("Bear", "Forest"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [Permanent(JAXIS), Permanent(BEAR), *lands(1)], [FOREST], [FOREST] * 5
        activate(game, a, "Discard a card")
        [token] = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertTrue(game.has_keyword(token, "haste"))
        end_step(game, a)
        self.assertEqual(([p.card.name for p in creatures(a)], len(a.hand)), (["Jaxis, the Troublemaker", "Bear"], 1))
