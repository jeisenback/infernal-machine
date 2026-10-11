"""Manifest dread: look at the top two cards, one enters face down as a 2/2 creature and the other goes to the graveyard."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, TURN_UP, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
SPELL = real("Manifest Dread", "{1}{G}", "Sorcery", "Manifest dread.")
TWINS = real("Unsettling Twins", "{3}{U}", "Creature — Human", "When this creature enters, manifest dread.", "3", "3")
FOUR = real("Dread Double", "{3}", "Sorcery", "Manifest dread twice.")
MASK = real("Killer's Mask", "{2}", "Artifact — Equipment", "When this Equipment enters, manifest dread, then attach this Equipment to that creature.\n"
            "Equipped creature gets +1/+0.\nEquip {2}")
DOOR = real("Gym", "{2}{G}", "Enchantment — Room", "When this enchantment enters, manifest dread, then put three +1/+1 counters on that creature.")
DOOR_ONE = real("Tunnel", "{1}", "Enchantment", "When this enchantment enters, manifest dread, then put a +1/+1 counter on that creature.")
BEASTIE = real("Bashful Beastie", "{3}{G}", "Creature — Beast", "When this creature dies, manifest dread.", "5", "4")


def cast(card, library, *answers, n=6):
    game, _ = table3(script(*answers))
    a, b, _ = game.seats
    a.hand, a.battlefield, a.library = [card], lands(n), list(library)
    game._perform(a, CAST + card.name)
    run_stack(game)
    game._check_state()
    return game, a, b


def face_down(seat):
    return [p for p in seat.battlefield if p.manifested]


class ParseTests(unittest.TestCase):
    def test_the_cards_and_their_riders_are_understood(self):
        for card in (SPELL, TWINS, FOUR, MASK, DOOR, DOOR_ONE, BEASTIE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ManifestDreadTests(unittest.TestCase):
    def test_the_chosen_card_is_a_face_down_creature_and_the_other_goes_to_the_graveyard(self):
        game, a, _ = cast(SPELL, [OGRE, FOREST, FOREST], "Ogre")
        [manifest] = face_down(a)
        self.assertEqual((manifest.real_card, game.power(manifest), game.toughness(manifest)), (OGRE, 2, 2))
        self.assertEqual(([c.name for c in a.graveyard], len(a.library)), (["Forest", "Manifest Dread"], 1))

    def test_choosing_the_other_card(self):
        game, a, _ = cast(SPELL, [OGRE, FOREST, FOREST], "Forest")
        [manifest] = face_down(a)
        self.assertEqual(manifest.real_card, FOREST)
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Manifest Dread", "Ogre"])

    def test_only_two_cards_are_looked_at(self):
        game, a, _ = cast(SPELL, [OGRE, BEAR, FOREST], "Bear")
        self.assertEqual([c.name for c in a.library], ["Forest"])

    def test_a_library_of_one_card_manifests_it_and_an_empty_one_does_nothing(self):
        game, a, _ = cast(SPELL, [OGRE])
        self.assertEqual(([p.real_card for p in face_down(a)], [c.name for c in a.graveyard]), ([OGRE], ["Manifest Dread"]))
        game, a, _ = cast(SPELL, [])
        self.assertEqual((face_down(a), [c.name for c in a.graveyard]), ([], ["Manifest Dread"]))

    def test_twice_manifests_two_creatures_from_four_cards(self):
        game, a, _ = cast(FOUR, [OGRE, BEAR, FOREST, FOREST, FOREST], "Ogre", "Forest")
        self.assertEqual(sorted(p.real_card.name for p in face_down(a)), ["Forest", "Ogre"])
        self.assertEqual((sorted(c.name for c in a.graveyard), len(a.library)), (["Bear", "Dread Double", "Forest"], 1))

    def test_it_is_a_creature_that_enters_with_the_ability_that_made_it(self):
        game, a, _ = cast(TWINS, [OGRE, FOREST], "Ogre")
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Face-down creature", "Unsettling Twins"])

    def test_a_manifested_creature_card_can_be_turned_face_up_for_its_cost(self):
        ogre = real("Big Ogre", "{2}", "Creature — Ogre", "", "3", "3")
        game, a, _ = cast(SPELL, [ogre, FOREST], "Big Ogre")
        [manifest] = face_down(a)
        label = TURN_UP + game.label(manifest)
        self.assertIn(label, game.legal_actions(a))
        game._perform(a, label)
        self.assertEqual((manifest.card, manifest.manifested), (ogre, False))

    def test_a_manifested_land_cannot_be_turned_up(self):
        game, a, _ = cast(SPELL, [FOREST, FOREST], "Forest")
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(TURN_UP)])

    def test_a_dying_manifest_goes_to_the_graveyard_as_the_card(self):
        game, a, _ = cast(SPELL, [OGRE, FOREST], "Ogre")
        [manifest] = face_down(a)
        game.destroy(manifest)
        self.assertIn("Ogre", [c.name for c in a.graveyard])


class RiderTests(unittest.TestCase):
    def test_counters_go_on_the_creature_just_manifested(self):
        game, a, _ = cast(DOOR, [OGRE, FOREST], "Ogre")
        [manifest] = face_down(a)
        self.assertEqual((manifest.counters.get("+1/+1"), game.power(manifest)), (3, 5))

    def test_a_single_counter(self):
        game, a, _ = cast(DOOR_ONE, [OGRE, FOREST], "Ogre")
        self.assertEqual(face_down(a)[0].counters.get("+1/+1"), 1)

    def test_no_counters_when_nothing_was_manifested(self):
        game, a, _ = cast(DOOR, [])
        self.assertEqual(face_down(a), [])

    def test_the_equipment_attaches_to_the_creature_just_manifested(self):
        game, a, _ = cast(MASK, [OGRE, FOREST], "Ogre")
        [manifest] = face_down(a)
        mask = next(p for p in a.battlefield if p.card.name == "Killer's Mask")
        self.assertIs(mask.attached_to, manifest)
        self.assertEqual(game.power(manifest), 3)

    def test_the_equipment_stays_loose_with_an_empty_library(self):
        game, a, _ = cast(MASK, [])
        mask = next(p for p in a.battlefield if p.card.name == "Killer's Mask")
        self.assertIsNone(mask.attached_to)

    def test_when_this_creature_dies_manifest_dread(self):
        game, _ = table3(script("Ogre"))
        a = game.seats[0]
        beastie = Permanent(BEASTIE)
        a.battlefield, a.library = [beastie], [OGRE, FOREST, FOREST]
        game.destroy(beastie)
        run_stack(game)
        self.assertEqual([p.real_card for p in face_down(a)], [OGRE])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bashful Beastie", "Forest"])


if __name__ == "__main__":
    unittest.main()
