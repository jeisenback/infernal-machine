import unittest

from infernal_machine import goldfish
from infernal_machine.bot import _cast_name
from infernal_machine.game import CAST, CAST_COMMANDER, CAST_PREPARED, PLAY_LAND, Permanent
from infernal_machine.zones import CAST_PREFIXES, LAND_PREFIXES, ZONE_PLAYS
from tests.helpers import table


class RegistryTests(unittest.TestCase):
    def test_no_prefix_hides_another(self):
        prefixes = [CAST, CAST_COMMANDER, CAST_PREPARED, PLAY_LAND, *CAST_PREFIXES, *LAND_PREFIXES]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for a in prefixes:
            for b in prefixes:
                self.assertTrue(a == b or not a.startswith(b), f"{a!r} starts with {b!r}: the wrong handler would take it")

    def test_every_zone_has_a_cast_prefix_and_all_but_the_spell_only_ones_a_land_prefix(self):
        self.assertEqual(len(ZONE_PLAYS), len(CAST_PREFIXES))
        self.assertEqual(len(LAND_PREFIXES), sum(bool(z.land_prefix) for z in ZONE_PLAYS))
        self.assertNotIn("", LAND_PREFIXES)  # (an empty prefix would match every action)

    def test_the_bot_reads_the_card_name_after_any_cast_prefix(self):
        for prefix in CAST_PREFIXES:
            self.assertEqual(_cast_name(prefix + "Some Card"), "Some Card", prefix)

    def test_the_goldfish_counts_every_zones_casts(self):
        for prefix in CAST_PREFIXES:
            self.assertIn(prefix, goldfish.CASTS)

    def test_a_zone_ignores_an_action_that_is_not_its_own(self):
        game, _, _ = table(None)
        seat = game.seats[0]
        for zone in ZONE_PLAYS:
            self.assertFalse(zone.perform(game, seat, CAST + "Anything"))
            self.assertFalse(zone.perform(game, seat, PLAY_LAND + "Anything"))

    def test_zones_offer_nothing_when_they_hold_nothing(self):
        game, _, _ = table(None)
        seat = game.seats[0]
        seat.battlefield = [Permanent(c) for c in []]
        seat.library = []
        for zone in ZONE_PLAYS:
            self.assertEqual(zone.offers(game, seat, True), [])


if __name__ == "__main__":
    unittest.main()
