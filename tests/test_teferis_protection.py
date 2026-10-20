"""Teferi's Protection, from its Oracle text: no life change, protection from everything, all your permanents phase out, exiled."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, real, run_stack, script, table3

PROTECTION = real("Teferi's Protection", "{2}{W}", "Instant",
                  "Until your next turn, your life total can't change and you gain protection from everything. All permanents you control phase out. "
                  "(While they're phased out, they're treated as though they don't exist. They phase in before you untap during your untap step.)\n"
                  "Exile Teferi's Protection.")
SWORD = real("Sword", "{3}", "Artifact — Equipment", "Equipped creature gets +2/+2.\nEquip {2}")


def cast():
    game, _ = table3(script(), script())
    a, b, c = game.seats
    bear = Permanent(BEAR, sick=False)
    sword = Permanent(SWORD, attached_to=bear)
    a.battlefield = lands(3) + [bear, sword]
    a.hand = [PROTECTION]
    b.battlefield = [Permanent(OGRE)]
    game._perform(a, CAST + "Teferi's Protection")
    run_stack(game)
    return game, a, b, c


class ProtectionTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PROTECTION), [])

    def test_everything_you_control_phases_out_with_what_is_attached(self):
        game, a, b, c = cast()
        self.assertEqual(a.battlefield, [])
        self.assertEqual(sorted(p.card.name for p in a.phased_out), ["Bear", "City of Brass", "City of Brass", "City of Brass", "Sword"])

    def test_other_players_keep_their_permanents(self):
        game, a, b, c = cast()
        self.assertEqual([p.card.name for p in b.battlefield], ["Ogre"])

    def test_the_spell_is_exiled_not_put_in_the_graveyard(self):
        game, a, b, c = cast()
        self.assertEqual(([x.name for x in a.exile], a.graveyard), (["Teferi's Protection"], []))

    def test_your_life_total_cannot_change(self):
        game, a, b, c = cast()
        game.change_life(a, -5)
        game.change_life(a, 7)
        game.damage(a, 4)
        self.assertEqual(a.life, 40)

    def test_nothing_can_target_you(self):
        game, a, b, c = cast()
        self.assertEqual([label for label, _ in game.target_options("player", b)], ["Player: B (seat 1)", "Player: C (seat 2)"])

    def test_others_life_still_changes(self):
        game, a, b, c = cast()
        game.change_life(b, -5)
        self.assertEqual(b.life, 35)

    def test_it_all_ends_when_your_next_turn_begins(self):
        game, a, b, c = cast()
        game.step = "untap"
        game._turn_based_actions(b)
        self.assertEqual((a.protected, a.life_locked, len(a.phased_out)), (True, True, 5))
        game._turn_based_actions(a)
        self.assertEqual((a.protected, a.life_locked, a.phased_out, len(a.battlefield)), (False, False, [], 5))
        game.change_life(a, -5)
        self.assertEqual(a.life, 35)

    def test_the_permanents_come_back_untapped_and_attached(self):
        game, a, b, c = cast()
        for p in a.phased_out:
            p.tapped = True
        game.step = "untap"
        game._turn_based_actions(a)
        bear = next(p for p in a.battlefield if p.card.name == "Bear")
        sword = next(p for p in a.battlefield if p.card.name == "Sword")
        self.assertEqual((sword.attached_to is bear, [p.tapped for p in a.battlefield]), (True, [False] * 5))

    def test_nothing_can_block_with_a_phased_out_creature(self):
        game, a, b, c = cast()
        self.assertEqual([p for p in a.battlefield if "Creature" in p.card.type_line], [])


if __name__ == "__main__":
    unittest.main()
