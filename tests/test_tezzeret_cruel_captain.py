"""Tezzeret, Cruel Captain: "0: Untap target artifact or creature. If it's an artifact creature, put a +1/+1 counter on it." and "−7: You
get an emblem with "At the beginning of combat on your turn, put three +1/+1 counters on target artifact you control. If it's not a
creature, it becomes a 0/0 Robot artifact creature."" """

import unittest

from infernal_machine.effects import TREASURE
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, begin, end_turn, lands, pick, real, run_stack, table3

TEZZERET = real("Tezzeret, Cruel Captain", "{3}", "Legendary Planeswalker — Tezzeret", "Whenever an artifact you control enters, put a "
                "loyalty counter on Tezzeret.\n0: Untap target artifact or creature. If it's an artifact creature, put a +1/+1 counter on "
                "it.\n−3: Search your library for an artifact card with mana value 1 or less, reveal it, put it into your hand, then "
                "shuffle.\n−7: You get an emblem with \"At the beginning of combat on your turn, put three +1/+1 counters on target "
                "artifact you control. If it's not a creature, it becomes a 0/0 Robot artifact creature.\"")
CRYSTAL_BALL = real("Crystal Ball", "{3}", "Artifact", "{1}, {T}: Scry 2. (Look at the top two cards of your library, then put any number "
                    "of them on the bottom and the rest on top in any order.)")
VOLTAIC_KEY = real("Voltaic Key", "{1}", "Artifact", "{1}, {T}: Untap target artifact.")
ORNITHOPTER = real("Ornithopter", "{0}", "Artifact Creature — Thopter", "Flying", "0", "2")


def table(target, loyalty=4):
    game, _ = table3(pick(target))
    a = game.seats[0]
    a.battlefield = [Permanent(TEZZERET, loyalty=loyalty)] + lands(3)
    return game, a


def activate(game, seat, loyalty):
    game._perform(seat, next(x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + "Tezzeret") and f"{loyalty}:" in x))
    run_stack(game)


class TezzeretCruelCaptainTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TEZZERET), [])

    def test_zero_untaps_an_artifact_creature_and_puts_a_counter_on_it(self):
        game, a = table("Ornithopter")
        thopter = Permanent(ORNITHOPTER, tapped=True)
        a.battlefield.append(thopter)
        activate(game, a, "0")
        self.assertEqual((thopter.tapped, thopter.counters.get("+1/+1", 0)), (False, 1))

    def test_zero_untaps_a_creature_or_an_artifact_without_a_counter(self):
        for card, name in ((BEAR, "Bear"), (CRYSTAL_BALL, "Crystal Ball")):
            game, a = table(name)
            permanent = Permanent(card, tapped=True)
            a.battlefield.append(permanent)
            activate(game, a, "0")
            self.assertEqual((permanent.tapped, permanent.counters.get("+1/+1", 0)), (False, 0), name)

    def test_another_untap_puts_no_counter_on_an_artifact_creature(self):
        game, a = table("Ornithopter")
        thopter = Permanent(ORNITHOPTER, tapped=True)
        a.battlefield = [Permanent(VOLTAIC_KEY), thopter] + lands(2)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Voltaic Key")))
        run_stack(game)
        self.assertEqual((thopter.tapped, thopter.counters.get("+1/+1", 0)), (False, 0))

    def test_the_emblem_keeps_the_artifacts_own_subtypes(self):
        game, a = table("Treasure", loyalty=7)
        treasure = Permanent(TREASURE)
        a.battlefield.append(treasure)
        activate(game, a, "−7")
        begin(game, "beginning_of_combat", a)
        self.assertEqual(treasure.card.type_line, "Token Artifact Creature — Treasure Robot")

    def test_the_emblem_makes_a_noncreature_artifact_a_robot_for_good(self):
        game, a = table("Crystal Ball", loyalty=7)
        ball = Permanent(CRYSTAL_BALL)
        a.battlefield.append(ball)
        activate(game, a, "−7")
        self.assertEqual(len(a.emblems), 1)
        begin(game, "beginning_of_combat", a)
        self.assertEqual((ball.card.type_line, game.power(ball), game.toughness(ball)), ("Artifact Creature — Robot", 3, 3))
        end_turn(game, a)  # no duration: it stays a creature
        self.assertEqual(ball.card.type_line, "Artifact Creature — Robot")

    def test_the_emblem_leaves_an_artifact_creature_what_it_is(self):
        game, a = table("Ornithopter", loyalty=7)
        thopter = Permanent(ORNITHOPTER)
        a.battlefield.append(thopter)
        activate(game, a, "−7")
        begin(game, "beginning_of_combat", a)
        self.assertEqual((thopter.card.type_line, game.power(thopter), game.toughness(thopter)), ("Artifact Creature — Thopter", 3, 5))


if __name__ == "__main__":
    unittest.main()
