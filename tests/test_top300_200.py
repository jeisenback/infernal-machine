"""The most played cards that were not playable (#200), batch 1: each from its own Oracle text, with cases where it must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, DISCARD_CARD_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, real
from tests.test_triggers_80 import BIG, FOREST, PLAINS

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
BEAR = Card(name="Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
SPARE = Card(name="Spare", mana_cost="{1}", cmc=1, type_line="Sorcery", oracle_text="Draw a card.")
SHRINE = Card(name="Shrine", mana_cost="{3}", cmc=3, type_line="Enchantment")
UNDERGROUND = Card(name="Underground Sea", type_line="Land — Island Swamp", produced_mana=("U", "B"))


def first(prefix):
    return lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith(prefix)), 0)


def on(seat, name):
    return next((p for p in seat.battlefield if p.card.name == name), None)


def names(cards):
    return sorted(c.name for c in cards)


CROP = real("Crop Rotation", "{G}", "Instant", "As an additional cost to cast this spell, sacrifice a land.\nSearch your library for a land card, "
            "put that card onto the battlefield, then shuffle.")
HARROW = real("Harrow", "{2}{G}", "Instant", "As an additional cost to cast this spell, sacrifice a land.\nSearch your library for up to two "
              "basic land cards, put them onto the battlefield, then shuffle.")
VISTA = Card(name="Prismatic Vista", type_line="Land", oracle_text="{T}, Pay 1 life, Sacrifice this land: Search your library for a basic land "
             "card, put it onto the battlefield, then shuffle.")
FEED = real("Feed the Swarm", "{1}{B}", "Sorcery", "Destroy target creature or enchantment an opponent controls. You lose life equal to that "
            "permanent's mana value.")
TORMENT = real("Withering Torment", "{2}{B}", "Instant", "Destroy target creature or enchantment. You lose 2 life.")
FRANTIC = real("Frantic Search", "{2}{U}", "Instant", "Draw two cards, then discard two cards. Untap up to three lands.")
SNAP = real("Snap", "{1}{U}", "Instant", "Return target creature to its owner's hand. Untap up to two lands.")
GAMBLE = real("Gamble", "{R}", "Sorcery", "Search your library for a card, put that card into your hand, discard a card at random, then shuffle.")
AETHERIZE = real("Aetherize", "{3}{U}", "Instant", "Return all attacking creatures to their owner's hand.")
OPAL = Card(name="Mox Opal", cmc=0, type_line="Legendary Artifact", oracle_text="Metalcraft — {T}: Add one mana of any color. Activate only if you "
            "control three or more artifacts.")
IDOL = Card(name="Idol of Oblivion", mana_cost="{2}", cmc=2, type_line="Artifact", oracle_text="{T}: Draw a card. Activate only if you created a "
            "token this turn.\n{8}, {T}, Sacrifice this artifact: Create a 10/10 colorless Eldrazi creature token.")
GARRUK = Card(name="Garruk's Uprising", mana_cost="{2}{G}", cmc=3, type_line="Enchantment", oracle_text="When this enchantment enters, if you "
              "control a creature with power 4 or greater, draw a card.\nCreatures you control have trample.\nWhenever a creature you control "
              "with power 4 or greater enters, draw a card.")
GRAY = Card(name="Gray Merchant of Asphodel", mana_cost="{3}{B}{B}", cmc=5, type_line="Creature — Zombie", power="2", toughness="4",
            oracle_text="When this creature enters, each opponent loses X life, where X is your devotion to black. You gain life equal to the "
            "life lost this way.")
HYBRID = Card(name="Hybrid", mana_cost="{B/R}{B/R}", cmc=2, type_line="Creature — Imp", power="1", toughness="1")
ARTIFACT = Card(name="Relic", mana_cost="{1}", cmc=1, type_line="Artifact")
MOX_A, MOX_B = Card(name="Mox A", type_line="Artifact"), Card(name="Mox B", type_line="Artifact")


class LandSearchTests(unittest.TestCase):
    def test_crop_rotation_sacrifices_a_land_and_puts_any_land_onto_the_battlefield_untapped(self):
        t = Table(CROP, n=2, library=[UNDERGROUND, FOREST], policy=first("Underground")).cast()
        self.assertEqual(len([p for p in t.a.battlefield if "Land" in p.card.type_line]), 2)  # one sacrificed, one fetched
        fetched = on(t.a, "Underground Sea")
        self.assertIsNotNone(fetched)
        self.assertFalse(fetched.tapped)

    def test_harrow_puts_two_basics_onto_the_battlefield_untapped(self):
        t = Table(HARROW, n=3, library=[FOREST, ISLAND, UNDERGROUND, SWAMP], policy=first("Forest")).cast()
        basics = [p for p in t.a.battlefield if p.card.name in ("Forest", "Island", "Swamp")]
        self.assertEqual(len(basics), 2)
        self.assertFalse(any(p.tapped for p in basics))
        self.assertIsNone(on(t.a, "Underground Sea"))  # not a basic

    def test_prismatic_vista_pays_life_and_fetches_an_untapped_basic(self):
        game, _ = table3(pick(ACTIVATE, "Forest"))
        a = game.seats[0]
        a.battlefield = [Permanent(VISTA)]
        a.library = [FOREST, SWAMP]
        life = a.life
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(a.life, life - 1)
        self.assertEqual([p.card.name for p in a.battlefield], ["Forest"])
        self.assertFalse(a.battlefield[0].tapped)


class DestroyTests(unittest.TestCase):
    def test_feed_the_swarm_destroys_an_opponents_creature_and_costs_its_mana_value(self):
        t = Table(FEED, n=2, theirs=[Permanent(BIG)], policy=first("Big")).cast()
        self.assertEqual(t.b.battlefield, [])
        self.assertEqual(t.a.life, 40 - int(BIG.cmc))

    def test_feed_the_swarm_takes_an_enchantment_too(self):
        t = Table(FEED, n=2, theirs=[Permanent(SHRINE)], policy=first("Shrine")).cast()
        self.assertEqual(t.b.battlefield, [])
        self.assertEqual(t.a.life, 40 - 3)

    def test_feed_the_swarm_cannot_target_your_own(self):
        t = Table(FEED, n=2, mine=[Permanent(BEAR)], theirs=[])
        self.assertNotIn(CAST + "Feed the Swarm", t.game.legal_actions(t.a))

    def test_withering_torment_destroys_a_creature_or_enchantment_and_costs_two(self):
        t = Table(TORMENT, n=3, theirs=[Permanent(SHRINE)], policy=first("Shrine")).cast()
        self.assertEqual((t.b.battlefield, t.a.life), ([], 38))
        t = Table(TORMENT, n=3, mine=[Permanent(BEAR)], policy=first("Bear")).cast()
        self.assertEqual(t.a.life, 38)

    def test_withering_torment_has_no_other_targets(self):
        t = Table(TORMENT, n=3, theirs=[Permanent(ARTIFACT)])
        self.assertNotIn(CAST + "Withering Torment", t.game.legal_actions(t.a))


class UntapTests(unittest.TestCase):
    def tap_all(self, seat):
        for p in seat.battlefield:
            p.tapped = True

    def test_frantic_search_draws_two_discards_two_and_untaps_up_to_three_lands(self):
        t = Table(FRANTIC, n=5, library=[SPARE, SPARE, SPARE, SPARE], policy=first("Spare"))
        t.cast()
        self.assertEqual((len(t.a.hand), len(t.a.graveyard)), (0, 3))  # Frantic Search itself plus two discards
        self.assertEqual(sum(not p.tapped for p in t.a.battlefield), 5)  # three were tapped for it and all three came back

    def test_it_untaps_only_as_many_as_there_are_tapped(self):
        t = Table(SNAP, n=2, theirs=[Permanent(BEAR)], policy=first("Bear"))
        t.cast()
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 0)

    def test_snap_returns_the_creature_and_untaps_two(self):
        t = Table(SNAP, n=4, theirs=[Permanent(BEAR)], policy=first("Bear"))
        t.cast()
        self.assertEqual(names(t.b.hand), ["Bear"])
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 0)  # two were tapped for Snap, both came back

    def test_only_up_to_the_number_asked_for_is_untapped(self):
        t = Table(SNAP, n=6, theirs=[Permanent(BEAR)], policy=first("Bear"))
        for p in t.a.battlefield[2:5]:
            p.tapped = True  # three more tapped lands besides the two Snap will be paid with
        t.cast()
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 3)  # five tapped, two untapped

    def test_a_tapped_nonland_is_left_alone(self):
        t = Table(SNAP, n=2, theirs=[Permanent(BEAR)], mine=[Permanent(ARTIFACT)], policy=first("Bear"))
        t.a.battlefield[0].tapped = True
        t.cast()
        self.assertTrue(t.a.battlefield[0].tapped)
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 1)

    def test_done_ends_the_choosing(self):
        asked = []

        def policy(prompt, options):
            if prompt.startswith("Untap which land"):
                asked.append(options)
                return len(options) - 1
            return first("Bear")(prompt, options)

        Table(SNAP, n=4, theirs=[Permanent(BEAR)], policy=policy).cast()
        self.assertEqual(len(asked), 1)

    def test_done_leaves_the_rest_tapped(self):
        def policy(prompt, options):
            if prompt.startswith("Untap which land"):
                return len(options) - 1  # Done
            return first("Bear")(prompt, options)

        t = Table(SNAP, n=4, theirs=[Permanent(BEAR)], policy=policy)
        t.cast()
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 2)


class GambleTests(unittest.TestCase):
    def test_it_finds_any_card_and_discards_one_at_random(self):
        t = Table(GAMBLE, n=1, library=[BIG, SPARE, BEAR], policy=first("Big"))
        t.a.hand += [SPARE]
        t.cast()
        self.assertEqual(len(t.a.hand), 1)  # Spare and Big in hand, one discarded
        self.assertEqual(len(t.a.graveyard), 2)  # Gamble and the discard
        self.assertEqual(len(t.a.library), 2)

    def test_the_discard_is_not_chosen(self):
        asked = []

        def policy(prompt, options):
            if prompt.startswith(DISCARD_CARD_PROMPT):
                asked.append(options)
            return first("Big")(prompt, options)

        t = Table(GAMBLE, n=1, library=[BIG, SPARE], policy=policy)
        t.a.hand += [SPARE]
        t.cast()
        self.assertEqual(asked, [])

    def test_with_only_the_found_card_that_one_is_discarded(self):
        t = Table(GAMBLE, n=1, library=[BIG], policy=first("Big")).cast()
        self.assertEqual((t.a.hand, names(t.a.graveyard)), ([], ["Big", "Gamble"]))


class AetherizeTests(unittest.TestCase):
    def test_attacking_creatures_return_to_their_owners_hands(self):
        t = Table(AETHERIZE, n=4, theirs=[Permanent(BEAR), Permanent(BIG)])
        t.game.combat.add_attacker(t.b.battlefield[0], t.b, t.a)
        t.cast()
        self.assertEqual(names(t.b.hand), ["Bear"])
        self.assertEqual([p.card.name for p in t.b.battlefield], ["Big"])  # it was not attacking

    def test_with_nothing_attacking_nothing_happens(self):
        t = Table(AETHERIZE, n=4, theirs=[Permanent(BEAR)]).cast()
        self.assertEqual([p.card.name for p in t.b.battlefield], ["Bear"])


class ManaTests(unittest.TestCase):
    def pay(self, mine):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in mine]
        return game._payment(a, Card(name="Spell", mana_cost="{G}", cmc=1, type_line="Instant"))

    def test_mox_opal_needs_three_artifacts(self):
        self.assertIsNone(self.pay([OPAL, MOX_A]))
        self.assertIsNotNone(self.pay([OPAL, MOX_A, MOX_B]))  # Opal counts itself

    def test_it_makes_a_mana_of_any_color(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in (OPAL, MOX_A, MOX_B)]
        for cost in ("{G}", "{U}", "{B}"):
            self.assertIsNotNone(game._payment(a, Card(name="Spell", mana_cost=cost, cmc=1, type_line="Instant")), cost)


class IdolTests(unittest.TestCase):
    def draw_actions(self, game, seat):
        return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and "Draw a card" in x]

    def test_it_needs_a_token_made_this_turn(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(IDOL)]
        a.battlefield[0].sick = False
        self.assertEqual(self.draw_actions(game, a), [])
        game.create_tokens(a, Card(name="Goblin", type_line="Token Creature — Goblin", power="1", toughness="1"), 1)
        self.assertEqual(len(self.draw_actions(game, a)), 1)

    def test_a_token_from_an_earlier_turn_does_not_count(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(IDOL)]
        a.battlefield[0].sick = False
        game.create_tokens(a, Card(name="Goblin", type_line="Token Creature — Goblin", power="1", toughness="1"), 1)
        game.turn += 1
        self.assertEqual(self.draw_actions(game, a), [])

    def test_an_opponents_token_does_not_count(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield = [Permanent(IDOL)]
        a.battlefield[0].sick = False
        game.create_tokens(b, Card(name="Goblin", type_line="Token Creature — Goblin", power="1", toughness="1"), 1)
        self.assertEqual(self.draw_actions(game, a), [])


class GarrukTests(unittest.TestCase):
    def enter(self, mine):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in mine]
        a.library = [FOREST] * 3
        game._enter(a, Permanent(GARRUK))
        run_stack(game)
        return len(a.hand)

    def test_it_draws_if_you_control_a_creature_with_power_four_or_greater(self):
        self.assertEqual(self.enter([BIG]), 1)  # BIG has power >= 4 in the shared fixtures

    def test_exactly_four_is_enough_and_three_is_not(self):
        four = Card(name="Four", mana_cost="{3}", cmc=3, type_line="Creature \u2014 Ogre", power="4", toughness="4")
        three = Card(name="Three", mana_cost="{3}", cmc=3, type_line="Creature \u2014 Ogre", power="3", toughness="3")
        self.assertEqual((self.enter([four]), self.enter([three])), (1, 0))

    def test_it_does_not_with_only_small_creatures(self):
        self.assertEqual(self.enter([BEAR]), 0)


class GrayMerchantTests(unittest.TestCase):
    def test_each_opponent_loses_life_equal_to_devotion_and_you_gain_it(self):
        t = Table(GRAY, n=5, mine=[Permanent(HYBRID)])
        t.cast()
        # Gray Merchant {B}{B} + the hybrid {B/R}{B/R}: devotion 4
        self.assertEqual((t.b.life, t.c.life, t.a.life), (36, 36, 48))  # each of two opponents loses 4; you gain all 8

    def test_devotion_counts_only_your_permanents_and_only_black(self):
        t = Table(GRAY, n=5, mine=[Permanent(BEAR)], theirs=[Permanent(HYBRID)])
        t.cast()
        self.assertEqual((t.b.life, t.a.life), (38, 44))  # just its own {B}{B}: 2 from each of two opponents


class ReportTests(unittest.TestCase):
    def test_the_cards_are_supported(self):
        for c in (CROP, HARROW, VISTA, FEED, TORMENT, FRANTIC, SNAP, GAMBLE, AETHERIZE, OPAL, IDOL, GARRUK, GRAY):
            with self.subTest(c.name):
                self.assertEqual(unsupported_lines(c), [])


if __name__ == "__main__":
    unittest.main()
