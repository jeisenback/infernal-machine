"""Cards whose every effect the engine already had, read from new wordings, from their real Oracle text: "At the beginning of each
player's draw step" (Kami of the Crescent Moon, Howling Mine), flickering one or more of your permanents (Displace, Ghostly Flicker),
"target artifact, enchantment, or land" (Acidic Slime), "spell, activated ability, or triggered ability" (Disallow), "Destroy all
artifacts, creatures, and enchantments." (Nevinyrral's Disk), In Garruk's Wake, Sword of Feast and Famine, Coastal Piracy, Mask of
Memory's "you may draw two cards. If you do, discard a card.", "Other artifact creatures you control" (Master of Etherium), "All
creatures have haste." (Concordant Crossroads) and "Untap target legendary permanent." (Minamo)."""

import unittest

from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, activate, enter, lands, pick, real, run_stack, table3

KAMI = real("Kami of the Crescent Moon", "{U}{U}", "Legendary Creature — Spirit", "At the beginning of each player's draw step, that "
            "player draws an additional card.", "1", "3", colors=("U",))
MINE = real("Howling Mine", "{2}", "Artifact", "At the beginning of each player's draw step, if this artifact is untapped, that player "
            "draws an additional card.")
GHOSTLY = real("Ghostly Flicker", "{2}{U}", "Instant", "Exile two target artifacts, creatures, and/or lands you control, then return "
               "those cards to the battlefield under your control.", colors=("U",))
DISPLACE = real("Displace", "{2}{U}", "Instant", "Exile up to two target creatures you control, then return those cards to the "
                "battlefield under their owner's control.", colors=("U",))
SLIME = real("Acidic Slime", "{3}{G}{G}", "Creature — Ooze", "Deathtouch (Any amount of damage this deals to a creature is enough to "
             "destroy it.)\nWhen this creature enters, destroy target artifact, enchantment, or land.", "2", "2", colors=("G",))
DISALLOW = real("Disallow", "{1}{U}{U}", "Instant", "Counter target spell, activated ability, or triggered ability. (Mana abilities "
                "can't be targeted.)", colors=("U",))
DISK = real("Nevinyrral's Disk", "{4}", "Artifact", "This artifact enters tapped.\n{1}, {T}: Destroy all artifacts, creatures, and "
            "enchantments.")
WAKE = real("In Garruk's Wake", "{7}{B}{B}", "Sorcery", "Destroy all creatures you don't control and all planeswalkers you don't "
            "control.", colors=("B",))
FEAST = real("Sword of Feast and Famine", "{3}", "Artifact — Equipment", "Equipped creature gets +2/+2 and has protection from black "
             "and from green.\nWhenever equipped creature deals combat damage to a player, that player discards a card and you untap "
             "all lands you control.\nEquip {2}")
PIRACY = real("Coastal Piracy", "{2}{U}{U}", "Enchantment", "Whenever a creature you control deals combat damage to an opponent, you "
              "may draw a card.", colors=("U",))
MASK = real("Mask of Memory", "{2}", "Artifact — Equipment", "Whenever equipped creature deals combat damage to a player, you may draw "
            "two cards. If you do, discard a card.\nEquip {1} ({1}: Attach to target creature you control. Equip only as a sorcery.)")
MASTER = real("Master of Etherium", "{2}{U}", "Artifact Creature — Vedalken Wizard", "Master of Etherium's power and toughness are each "
              "equal to the number of artifacts you control.\nOther artifact creatures you control get +1/+1.", "*", "*", colors=("U",))
CROSSROADS = real("Concordant Crossroads", "{G}", "World Enchantment", "All creatures have haste.", colors=("G",))
MINAMO = real("Minamo, School at Water's Edge", "", "Legendary Land", "{T}: Add {U}.\n{U}, {T}: Untap target legendary permanent.")
GOLEM = real("Golem", "{3}", "Artifact Creature — Golem", "", "3", "3")
SHRINE = real("Shrine", "{2}", "Enchantment", "")


class ParseOnlyTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (KAMI, MINE, GHOSTLY, DISPLACE, SLIME, DISALLOW, DISK, WAKE, FEAST, PIRACY, MASK, MASTER, CROSSROADS, MINAMO):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_each_players_draw_step_gives_that_player_a_card(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(KAMI)]
        for seat in (a, b):  # its controller's own step, and an opponent's
            seat.library = [FOREST] * 3
            game.happened("draw_step", seat)
            run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 1))

    def test_howling_mine_gives_nothing_while_tapped(self):
        for tapped, drawn in ((False, 1), (True, 0)):
            game, _ = table3()
            a, b, _ = game.seats
            a.battlefield, b.library = [Permanent(MINE, tapped=tapped)], [FOREST] * 3
            game.happened("draw_step", b)
            run_stack(game)
            self.assertEqual(len(b.hand), drawn, tapped)

    def test_ghostly_flicker_brings_back_two_different_permanents(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or 0)
        a = game.seats[0]
        golem, relic = Permanent(GOLEM, sick=False), Permanent(RELIC)
        a.battlefield, a.hand = [golem, relic, *lands(3)], [GHOSTLY]
        game._perform(a, CAST + "Ghostly Flicker")
        run_stack(game)
        names = [p.card.name for p in a.battlefield]
        self.assertEqual((names.count("Golem"), names.count("Relic")), (1, 1))
        self.assertFalse(any(p is golem or p is relic for p in a.battlefield))  # new objects (CR 400.7)

    def test_displace_may_take_only_one(self):
        game, _ = table3(pick("Bear", "No target"))
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = [bear, *lands(3)], [DISPLACE]
        game._perform(a, CAST + "Displace")
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield if p.card is BEAR], bear in a.battlefield), (["Bear"], False))

    def test_acidic_slime_can_destroy_a_land(self):
        game, _ = table3(pick("Forest"))
        a, b, _ = game.seats
        b.battlefield = [Permanent(FOREST), Permanent(BEAR)]
        enter(game, a, SLIME)
        run_stack(game)
        self.assertEqual([p.card.name for p in b.battlefield], ["Bear"])

    def test_disallow_counters_a_spell(self):
        game, _ = table3(pick("Spell: Bear"))
        a, b, _ = game.seats
        a.battlefield, a.hand = lands(3), [DISALLOW]
        game.stack.append(StackItem(BEAR, b))
        game._perform(a, CAST + "Disallow")
        game._resolve(game.stack.pop())
        self.assertEqual((game.stack, [c.name for c in b.graveyard]), ([], ["Bear"]))

    def test_nevinyrrals_disk_spares_lands(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(DISK), Permanent(GOLEM), Permanent(SHRINE), *lands(1)]
        b.battlefield = [Permanent(BEAR), Permanent(FOREST)]
        activate(game, a, "Nevinyrral's Disk")
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], [p.card.name for p in b.battlefield]), (["City of Brass"], ["Forest"]))

    def test_in_garruks_wake_spares_your_own_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, a.hand, b.battlefield = [Permanent(OGRE), *lands(9)], [WAKE], [Permanent(BEAR)]
        game._perform(a, CAST + "In Garruk's Wake")
        run_stack(game)
        self.assertEqual(("Ogre" in [p.card.name for p in a.battlefield], b.battlefield), (True, []))

    def test_sword_of_feast_and_famine_untaps_only_your_lands(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        mine, theirs = Permanent(FOREST, tapped=True), Permanent(FOREST, tapped=True)
        a.battlefield, b.battlefield, b.hand = [bear, Permanent(FEAST, attached_to=bear), mine], [theirs], [OGRE]
        game.damage(b, 4, bear, combat=True)
        run_stack(game)
        self.assertEqual((b.hand, mine.tapped, theirs.tapped), ([], False, True))

    def test_coastal_piracy_draws_when_your_creature_hits_an_opponent(self):
        game, _ = table3(pick("Yes"))
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        a.battlefield, a.library = [bear, Permanent(PIRACY)], [FOREST] * 2
        game.damage(b, 2, bear, combat=True)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_mask_of_memory_draws_two_and_discards_one_only_if_you_do(self):
        for answer, hand in (("Yes", 1), ("No", 0)):
            game, _ = table3(pick(answer))
            a, b, _ = game.seats
            bear = Permanent(BEAR)
            a.battlefield, a.library = [bear, Permanent(MASK, attached_to=bear)], [FOREST] * 3
            game.damage(b, 2, bear, combat=True)
            run_stack(game)
            self.assertEqual((len(a.hand), len(a.graveyard)), (hand, hand), answer)

    def test_master_of_etherium_pumps_other_artifact_creatures_only(self):
        game, _ = table3()
        a = game.seats[0]
        master, golem, bear = Permanent(MASTER), Permanent(GOLEM), Permanent(BEAR)
        a.battlefield = [master, golem, bear]
        self.assertEqual((game.power(golem), game.power(bear), game.power(master)), (4, 2, 2))  # two artifacts: Master is 2/2

    def test_concordant_crossroads_gives_every_players_creatures_haste(self):
        game, _ = table3()
        a, b, _ = game.seats
        theirs = Permanent(BEAR)
        a.battlefield, b.battlefield = [Permanent(CROSSROADS)], [theirs]
        self.assertTrue(game.has_keyword(theirs, "haste"))

    def test_minamo_untaps_only_a_legendary_permanent(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or pick("Kami")(prompt, options))
        a = game.seats[0]
        kami, bear = Permanent(KAMI, tapped=True), Permanent(BEAR, tapped=True)
        a.battlefield = [Permanent(MINAMO), kami, bear, *lands(1)]
        activate(game, a, "Minamo")
        run_stack(game)
        self.assertNotIn("Bear", " ".join(o for options in asked for o in options))
        self.assertEqual((kami.tapped, bear.tapped), (False, True))


if __name__ == "__main__":
    unittest.main()
