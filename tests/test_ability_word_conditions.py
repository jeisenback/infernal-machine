"""Ability-word conditions, batch 1, from the cards' real Oracle text: Dispatch's metalcraft "exile that creature" (the creature the first
sentence tapped), Puresteel Paladin's "Equipment you control have equip {0} as long as ...", the delirium searches of Demonic Counsel and
Traverse the Ulvenwald (the second search replaces the first), Stitch Together's threshold "to the battlefield instead", Putrid Imp's
"gets +1/+1 and can't block" while threshold holds, Adventuring Gear's landfall pump of the creature it equips, and Drag to the Roots'
"This spell costs {2} less to cast as long as ..." (delirium)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.common import CANT_BLOCK
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, SHRINE, activate, enter, lands, pick, real, run_stack, table3

DISPATCH = real("Dispatch", "{W}", "Instant", "Tap target creature.\nMetalcraft — If you control three or more artifacts, exile that creature.",
                colors=("W",))
PALADIN = real("Puresteel Paladin", "{W}{W}", "Creature — Human Knight", "Whenever an Equipment you control enters, you may draw a card.\n"
               "Metalcraft — Equipment you control have equip {0} as long as you control three or more artifacts.", "2", "2", colors=("W",))
COUNSEL = real("Demonic Counsel", "{1}{B}", "Sorcery", "Search your library for a Demon card, reveal it, put it into your hand, then shuffle.\n"
               "Delirium — If there are four or more card types among cards in your graveyard, instead search your library for any card, put "
               "it into your hand, then shuffle.", colors=("B",))
TRAVERSE = real("Traverse the Ulvenwald", "{G}", "Sorcery", "Search your library for a basic land card, reveal it, put it into your hand, then "
                "shuffle.\nDelirium — If there are four or more card types among cards in your graveyard, instead search your library for a "
                "creature or land card, reveal it, put it into your hand, then shuffle.", colors=("G",))
STITCH = real("Stitch Together", "{B}{B}", "Sorcery", "Return target creature card from your graveyard to your hand.\nThreshold — Return that "
              "card from your graveyard to the battlefield instead if there are seven or more cards in your graveyard.", colors=("B",))
IMP = real("Putrid Imp", "{B}", "Creature — Zombie Imp", "Discard a card: This creature gains flying until end of turn.\nThreshold — As long as "
           "there are seven or more cards in your graveyard, this creature gets +1/+1 and can't block.", "1", "1", colors=("B",))
GEAR = real("Adventuring Gear", "{1}", "Artifact — Equipment", "Landfall — Whenever a land you control enters, equipped creature gets +2/+2 "
            "until end of turn.\nEquip {1} ({1}: Attach to target creature you control. Equip only as a sorcery.)")
ROOTS = real("Drag to the Roots", "{2}{B}{G}", "Instant", "Delirium — This spell costs {2} less to cast as long as there are four or more card "
             "types among cards in your graveyard.\nDestroy target nonland permanent.", colors=("B", "G"))
CARDS = (DISPATCH, PALADIN, COUNSEL, TRAVERSE, STITCH, IMP, GEAR, ROOTS)

DELIRIUM = [FOREST, BEAR, RELIC, SHRINE]  # a land, a creature, an artifact and an enchantment: four card types
DEMON = Card(name="Demon", mana_cost="{2}{B}", type_line="Creature — Demon", power="4", toughness="4")


def cast(game, seat, card, n=6):
    seat.battlefield += lands(n)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


def hand_names(seat):
    return sorted(c.name for c in seat.hand)


class AbilityWordConditionTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_dispatch_exiles_the_tapped_creature_only_with_metalcraft(self):
        for artifacts, exiled in ((3, True), (2, False)):
            game, _ = table3(pick("Ogre"))
            a, b, _ = game.seats
            ogre = Permanent(OGRE)
            b.battlefield = [ogre]
            a.battlefield = [Permanent(RELIC) for _ in range(artifacts)]
            cast(game, a, DISPATCH, n=1)
            self.assertEqual((ogre in b.battlefield, ogre.tapped), (not exiled, True), artifacts)

    def test_puresteel_paladin_makes_equip_free_with_metalcraft(self):
        for artifacts, offered in ((3, True), (2, False)):  # the Gear and one or two more artifacts; no lands to pay {1}
            game, _ = table3(pick("Bear"))
            a = game.seats[0]
            bear = Permanent(BEAR)
            gear = Permanent(GEAR)
            a.battlefield = [Permanent(PALADIN), bear, gear] + [Permanent(RELIC) for _ in range(artifacts - 1)]
            equip = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Adventuring Gear" in x]
            self.assertEqual(bool(equip), offered, artifacts)
            if offered:
                activate(game, a, "Adventuring Gear")
                self.assertIs(gear.attached_to, bear)

    def test_demonic_counsel_finds_any_card_only_with_delirium(self):
        for graveyard, found in ((DELIRIUM, "Ogre"), (DELIRIUM[:3], "Demon")):  # three card types: only the Demon may be found
            game, _ = table3(pick("Ogre", "Demon"))
            a = game.seats[0]
            a.graveyard, a.library = list(graveyard), [DEMON, OGRE, FOREST]
            cast(game, a, COUNSEL)
            self.assertEqual(hand_names(a), [found], len(graveyard))

    def test_traverse_the_ulvenwald_finds_a_creature_with_delirium(self):
        for graveyard, found in ((DELIRIUM, "Ogre"), ([], "Forest")):
            game, _ = table3(pick("Ogre", "Forest"))
            a = game.seats[0]
            a.graveyard, a.library = list(graveyard), [OGRE, FOREST]
            cast(game, a, TRAVERSE)
            self.assertEqual(hand_names(a), [found], len(graveyard))

    def test_stitch_together_returns_to_the_battlefield_with_threshold(self):
        for filler, onto in ((6, True), (5, False)):  # with the Ogre itself: seven cards, then six
            game, _ = table3(pick("Ogre"))
            a = game.seats[0]
            a.graveyard = [OGRE] + [FOREST] * filler
            cast(game, a, STITCH)
            on_battlefield = any(p.card is OGRE for p in a.battlefield)
            self.assertEqual((on_battlefield, OGRE in a.hand), (onto, not onto), filler)

    def test_putrid_imp_grows_and_cant_block_with_threshold(self):
        game, _ = table3()
        a = game.seats[0]
        imp = Permanent(IMP)
        a.battlefield, a.graveyard = [imp], [FOREST] * 6
        self.assertEqual((game.power(imp), game.has_keyword(imp, CANT_BLOCK)), (1, False))
        a.graveyard.append(FOREST)
        self.assertEqual((game.power(imp), game.toughness(imp), game.has_keyword(imp, CANT_BLOCK)), (2, 2, True))

    def test_adventuring_gear_pumps_the_creature_it_equips_on_landfall(self):
        game, _ = table3()
        a = game.seats[0]
        bear, other = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [bear, other, Permanent(GEAR, attached_to=bear)]
        enter(game, a, FOREST)
        run_stack(game)
        self.assertEqual((game.power(bear), game.power(other)), (4, 2))

    def test_unattached_adventuring_gear_pumps_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(GEAR)]
        enter(game, a, FOREST)
        run_stack(game)
        self.assertEqual(game.power(bear), 2)

    def test_drag_to_the_roots_costs_2_less_with_delirium(self):
        for graveyard, offered in ((DELIRIUM, True), (DELIRIUM[:3], False)):
            game, _ = table3()
            a, b, _ = game.seats
            a.graveyard, a.hand, a.battlefield = list(graveyard), [ROOTS], lands(2)
            b.battlefield = [Permanent(OGRE)]
            self.assertEqual(any(x.startswith(CAST + ROOTS.name) for x in game.legal_actions(a)), offered, len(graveyard))


if __name__ == "__main__":
    unittest.main()
