"""Library search and look, from the cards' real Oracle text: Riveteers Overlook (sacrifice it; when you do, search and gain 1 life), Krosan
Verge (a Forest card and a Plains card), Goblin Engineer and Unmarked Grave (search into the graveyard), Coiling Oracle (a land onto the
battlefield, anything else into the hand), Satyr Wayfinder (a land from the top four), Survival of the Fittest (the cost "Discard a creature
card"), Monumental Henge (a historic card) and Elixir of Immortality (shuffle it and the graveyard into the library)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, PLAINS, RELIC, SWAMP, activate, enter, lands, pick, real, run_stack, table3

OVERLOOK = real("Riveteers Overlook", "", "Land", "When this land enters, sacrifice it. When you do, search your library for a basic Swamp, "
                "Mountain, or Forest card, put it onto the battlefield tapped, then shuffle and you gain 1 life.")
VERGE = real("Krosan Verge", "", "Land", "This land enters tapped.\n{T}: Add {C}.\n{2}, {T}, Sacrifice this land: Search your library for a "
             "Forest card and a Plains card, put them onto the battlefield tapped, then shuffle.")
ENGINEER = real("Goblin Engineer", "{1}{R}", "Creature — Goblin Artificer", "When this creature enters, you may search your library for an "
                "artifact card, put it into your graveyard, then shuffle.\n{R}, {T}, Sacrifice an artifact: Return target artifact card with "
                "mana value 3 or less from your graveyard to the battlefield.", "1", "2", colors=("R",))
GRAVE = real("Unmarked Grave", "{1}{B}", "Sorcery", "Search your library for a nonlegendary card, put that card into your graveyard, then "
             "shuffle.", colors=("B",))
ORACLE = real("Coiling Oracle", "{G}{U}", "Creature — Snake Elf Druid", "When this creature enters, reveal the top card of your library. If "
              "it's a land card, put it onto the battlefield. Otherwise, put that card into your hand.", "1", "1", colors=("G", "U"))
WAYFINDER = real("Satyr Wayfinder", "{1}{G}", "Creature — Satyr", "When this creature enters, reveal the top four cards of your library. You "
                 "may put a land card from among them into your hand. Put the rest into your graveyard.", "1", "1", colors=("G",))
SURVIVAL = real("Survival of the Fittest", "{1}{G}", "Enchantment", "{G}, Discard a creature card: Search your library for a creature card, "
                "reveal that card, put it into your hand, then shuffle.", colors=("G",))
HENGE = real("Monumental Henge", "", "Land", "This land enters tapped unless you control a Plains.\n{T}: Add {W}.\n{2}{W}{W}, {T}: Look at the "
             "top five cards of your library. You may reveal a historic card from among them and put it into your hand. Put the rest on the "
             "bottom of your library in a random order. (Artifacts, legendaries, and Sagas are historic.)")
ELIXIR = real("Elixir of Immortality", "{1}", "Artifact", "{2}, {T}: You gain 5 life. Shuffle this artifact and your graveyard into their "
              "owner's library.")
CARDS = (OVERLOOK, VERGE, ENGINEER, GRAVE, ORACLE, WAYFINDER, SURVIVAL, HENGE, ELIXIR)

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
LEGEND = real("Isamaru, Hound of Konda", "{W}", "Legendary Creature — Dog", "", "2", "2", colors=("W",))


def names(cards):
    return sorted(c.name for c in cards)


def battlefield(seat):
    return sorted(p.card.name for p in seat.battlefield)


class LibraryBatchTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_riveteers_overlook_is_sacrificed_for_a_basic_land_and_1_life(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [ISLAND, SWAMP]  # an Island is not one it may find
        enter(game, a, OVERLOOK)
        run_stack(game)
        self.assertEqual((battlefield(a), names(a.graveyard), a.life, names(a.library)), (["Swamp"], ["Riveteers Overlook"], 41, ["Island"]))
        self.assertTrue(a.battlefield[0].tapped)

    def test_riveteers_overlook_gone_before_its_trigger_resolves_finds_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [SWAMP]
        overlook = enter(game, a, OVERLOOK)
        game.destroy(overlook)  # not sacrificed: no "when you do"
        run_stack(game)
        self.assertEqual((battlefield(a), a.life, names(a.library)), ([], 40, ["Swamp"]))

    def test_krosan_verge_finds_a_forest_and_a_plains(self):
        for library, found in (([FOREST, FOREST, PLAINS], ["Forest", "Plains"]), ([PLAINS, SWAMP], ["Plains"])):  # no Forest: the Plains still
            game, _ = table3()
            a = game.seats[0]
            a.battlefield, a.library = [Permanent(VERGE)] + lands(2), list(library)
            activate(game, a, "Search your library")
            self.assertEqual([n for n in battlefield(a) if n in ("Forest", "Plains")], found, library)
            self.assertNotIn("Krosan Verge", battlefield(a))

    def test_goblin_engineer_puts_an_artifact_into_the_graveyard(self):
        game, _ = table3(pick("Yes", "Relic"))
        a = game.seats[0]
        a.library = [BEAR, RELIC]
        enter(game, a, ENGINEER)
        run_stack(game)
        self.assertEqual((names(a.graveyard), names(a.library)), (["Relic"], ["Bear"]))

    def test_unmarked_grave_finds_only_a_nonlegendary_card(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [LEGEND, OGRE]  # the first offered would be the legend, if it were
        a.battlefield = lands(2)
        a.hand = [GRAVE]
        game._perform(a, CAST + GRAVE.name)
        run_stack(game)
        self.assertEqual((names(a.graveyard), names(a.library)), (["Ogre", "Unmarked Grave"], ["Isamaru, Hound of Konda"]))

    def test_coiling_oracle_puts_a_land_onto_the_battlefield_and_anything_else_into_the_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST, OGRE]
        enter(game, a, ORACLE)
        run_stack(game)
        self.assertEqual((battlefield(a), names(a.hand)), (["Coiling Oracle", "Forest"], []))
        enter(game, a, ORACLE)
        run_stack(game)
        self.assertEqual((names(a.hand), a.drawn_cards), (["Ogre"], []))  # put into the hand, not drawn

    def test_satyr_wayfinder_takes_a_land_and_mills_the_rest(self):
        game, _ = table3(pick("Forest"))
        a = game.seats[0]
        a.library = [BEAR, FOREST, OGRE, RELIC, SWAMP]
        enter(game, a, WAYFINDER)
        run_stack(game)
        self.assertEqual((names(a.hand), names(a.graveyard), names(a.library)), (["Forest"], ["Bear", "Ogre", "Relic"], ["Swamp"]))

    def test_survival_of_the_fittest_discards_only_a_creature_card(self):
        game, _ = table3(pick("Ogre"))
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(SURVIVAL)] + lands(1), [OGRE]
        a.hand = [FOREST]  # no creature card: the ability can't be activated
        self.assertFalse(any("Discard a creature card" in action for action in game.legal_actions(a)))
        a.hand = [FOREST, BEAR]
        activate(game, a, "Discard a creature card")
        self.assertEqual((names(a.hand), names(a.graveyard)), (["Forest", "Ogre"], ["Bear"]))

    def test_monumental_henge_takes_a_historic_card(self):
        for library, taken in (([BEAR, RELIC, OGRE], ["Relic"]), ([BEAR, OGRE, FOREST], [])):
            game, _ = table3(pick("Relic"))
            a = game.seats[0]
            a.battlefield, a.library = [Permanent(HENGE)] + lands(4), list(library)
            activate(game, a, "Look at the top five")
            self.assertEqual(names(a.hand), taken, library)

    def test_elixir_of_immortality_shuffles_itself_and_the_graveyard_into_the_library(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield, a.graveyard, a.library = [Permanent(ELIXIR)] + lands(2), [BEAR, OGRE], [FOREST]
        b.graveyard = [RELIC]  # another player's graveyard stays
        activate(game, a, "You gain 5 life")
        self.assertEqual((a.life, names(a.library), a.graveyard, names(b.graveyard)),
                         (45, ["Bear", "Elixir of Immortality", "Forest", "Ogre"], [], ["Relic"]))


if __name__ == "__main__":
    unittest.main()
