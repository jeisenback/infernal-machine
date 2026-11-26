"""Level up (CR 702.87) and levelers (CR 711), from the cards' real Oracle text. All 21 cards whose only gap it was are fully playable.
"Level up {1}" is "{1}: Put a level counter on this creature. Activate only as a sorcery." A leveler reads as the band its level
counters are in: Hexdrinker (2/1) with no counters has no protection; with three it is a 4/4 with protection from instants; with eight a
6/6 with protection from everything. Coralhelm Commander at level 2 is a 3/3 with flying, at level 4 a 4/4 that gives other Merfolk
+1/+1, and it doesn't before. Counters from anywhere count (put or removed); Kazandu Tuskcaller's "{T}: Create a 3/3 Elephant" is
offered only in its band; the card in the graveyard is the whole card again. Level up is offered only at sorcery speed. Level counters
moved onto it count too, and a manifested Hexdrinker turned face up is a 2/1 with no protection until it has counters."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from tests.helpers import activate, lands, real, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Beastbreaker of Bala Ged", "Brimstone Mage", "Caravan Escort", "Coralhelm Commander", "Enclave Cryptologist",
         "Guul Draz Assassin", "Hada Spy Patrol", "Halimar Wavewatch", "Hexdrinker", "Ikiral Outrider", "Kabira Vindicator",
         "Kargan Dragonlord", "Kazandu Tuskcaller", "Knight of Cliffhaven", "Lighthouse Chronologist", "Nirkana Cutthroat", "Null Champion",
         "Skywatcher Adept", "Student of Warfare", "Transcendent Master", "Zulaport Enforcer"]
HEX, CORAL, TUSK = REAL["Hexdrinker"], REAL["Coralhelm Commander"], REAL["Kazandu Tuskcaller"]
MERFOLK = real("Merrow", "{U}", "Creature \u2014 Merfolk", "", "1", "1")

# The guards these tests are there to catch (python tools/mutate.py tests.test_level_up).
MUTATIONS = [
    ("infernal_machine/effects/statics.py", "inside = int(m[1]) <= level and (m[2] is None or level <= int(m[2]))",
     "inside = int(m[1]) <= level", "only its own band"),
    ("infernal_machine/game.py", '        if counter == "level":\n            self._relevel(permanent)', "", "a counter put changes the band"),
    ("infernal_machine/game.py", '                if kind == "level":\n                    self._relevel(permanent)', "", "a counter removed too"),
    ("infernal_machine/game.py", "        elif is_leveler(permanent.card) and permanent.real_card is None:", "        elif False:",
     "it enters reading as its band"),
    ("infernal_machine/report.py", "        if is_level_band_line(line) and is_leveler(card):", "        if False:", "the band lines are read"),
    ("infernal_machine/game.py", '        if counter == "level":\n            self._relevel(destination)', "", "counters moved onto it"),
    ("infernal_machine/game.py", "        if is_leveler(permanent.card):  # CR 711.2: a leveler turned face up", "        if False:  # CR 711.2: a leveler turned face up",
     "turned face up"),
]


def leveler(card, level=0):
    game, _ = table3()
    a = game.seats[0]
    permanent = Permanent(card, sick=False)
    game._enter(a, permanent)
    if level:
        game.put_counters(permanent, "level", level)
    return game, a, permanent


def size(game, permanent):
    return game.power(permanent), game.toughness(permanent)


class LevelUpTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_each_band_has_its_own_size_and_abilities(self):
        for level, expected in ((0, ((2, 1), False, False)), (3, ((4, 4), True, False)), (7, ((4, 4), True, False)),
                                (8, ((6, 6), False, True))):
            game, _, hex_ = leveler(HEX, level)
            self.assertEqual((size(game, hex_), game.has_keyword(hex_, "protection from instants"),
                              game.has_keyword(hex_, "protection from everything")), expected, level)

    def test_level_up_puts_a_counter_at_sorcery_speed(self):
        game, a, coral = leveler(CORAL, 1)
        a.battlefield += lands(1)
        activate(game, a, "level counter")
        self.assertEqual((coral.counters["level"], size(game, coral), game.has_keyword(coral, "flying")), (2, (3, 3), True))
        game.active = 1  # (another player's turn: not at sorcery speed)
        self.assertFalse(any(x.startswith(ACTIVATE) and "level counter" in x for x in game.legal_actions(a)))

    def test_the_top_band_gives_other_merfolk_plus_one(self):
        game, a, coral = leveler(CORAL, 3)
        merrow = Permanent(MERFOLK)
        a.battlefield.append(merrow)
        self.assertEqual(size(game, merrow), (1, 1))
        game.put_counters(coral, "level", 1)
        self.assertEqual((size(game, coral), size(game, merrow)), ((4, 4), (2, 2)))
        game.remove_counters(coral, "level", 2)
        self.assertEqual((size(game, coral), size(game, merrow), game.has_keyword(coral, "flying")), ((3, 3), (1, 1), True))

    def test_a_bands_activated_ability_only_in_its_band(self):
        game, a, tusk = leveler(TUSK)
        self.assertFalse(any("Elephant" in x for x in game.legal_actions(a)))
        game.put_counters(tusk, "level", 2)
        self.assertTrue(any("Elephant" in x for x in game.legal_actions(a)))

    def test_level_counters_moved_onto_it_change_its_band(self):
        game, a, giver = leveler(HEX, 3)
        taker = Permanent(HEX, sick=False)
        game._enter(a, taker)
        game.move_counters(giver, taker, "level", None)
        self.assertEqual((size(game, giver), size(game, taker), game.has_keyword(taker, "protection from instants")),
                         ((2, 1), (4, 4), True))

    def test_turned_face_up_it_reads_as_its_band(self):
        game, _ = table3()
        a = game.seats[0]
        a.library, a.battlefield = [HEX], lands(1)
        game.manifest(a)
        (hex_,) = [p for p in a.battlefield if p.manifested]
        game.turn_face_up(a, hex_)
        self.assertEqual((size(game, hex_), game.has_keyword(hex_, "protection from everything")), ((2, 1), False))
        game.put_counters(hex_, "level", 8)
        self.assertEqual((size(game, hex_), game.has_keyword(hex_, "protection from everything")), ((6, 6), True))

    def test_it_leaves_as_the_whole_card(self):
        game, a, hex_ = leveler(HEX, 3)
        game.destroy(hex_)
        self.assertEqual([c is HEX for c in a.graveyard], [True])


if __name__ == "__main__":
    unittest.main()
