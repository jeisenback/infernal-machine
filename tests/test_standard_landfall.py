"""Standard's landfall decks, from their cards' real Oracle text: Sapling Nursery ("Affinity for Forests"; Treefolk and Forests gain
indestructible), Keen-Eyed Curator (card types among the cards exiled with it), Pit of Offerings (exile up to three cards from graveyards;
mana of their colors) and Esper Origins (cast from a graveyard, it comes back as Summon: Esper Maduin, a Saga creature)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, PLAY_LAND, Permanent
from infernal_machine.mana import cost_of
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, real, run_stack, script, table3

NURSERY = real("Sapling Nursery", "{6}{G}{G}", "Enchantment", "Affinity for Forests (This spell costs {1} less to cast for each Forest you "
               "control.)\nLandfall — Whenever a land you control enters, create a 3/4 green Treefolk creature token with reach.\n{1}{G}, "
               "Exile this enchantment: Treefolk and Forests you control gain indestructible until end of turn.", colors=("G",))
CURATOR = real("Keen-Eyed Curator", "{G}{G}", "Creature — Raccoon Scout", "As long as there are four or more card types among cards exiled "
               "with this creature, it gets +4/+4 and has trample.\n{1}: Exile target card from a graveyard.", "3", "3", colors=("G",))
PIT = Card(name="Pit of Offerings", type_line="Land — Cave", produced_mana=("B", "C", "G", "R", "U", "W"),
           oracle_text="This land enters tapped.\nWhen this land enters, exile up to three target cards from graveyards.\n{T}: Add {C}.\n"
                       "{T}: Add one mana of any of the exiled cards' colors.")
MADUIN = Card(name="Summon: Esper Maduin", type_line="Enchantment Creature — Saga Elemental", colors=("G",), power="4", toughness="4",
              oracle_text="(As this Saga enters and after your draw step, add a lore counter. Sacrifice after III.)\nI — Reveal the top card "
                          "of your library. If it's a permanent card, put it into your hand.\nII — Add {G}{G}.\nIII — Other creatures you "
                          "control get +2/+2 and gain trample until end of turn.")
ORIGINS = Card(name="Esper Origins // Summon: Esper Maduin", mana_cost="{1}{G}", cmc=2.0, type_line="Sorcery", colors=("G",), flip=MADUIN,
               oracle_text="Surveil 2. You gain 2 life. If this spell was cast from a graveyard, exile it, then put it onto the battlefield "
                           "transformed under its owner's control with a finality counter on it. (If a creature with a finality counter on "
                           "it would die, exile it instead.)\nFlashback {3}{G} (You may cast this card from your graveyard for its flashback "
                           "cost. Then exile it.)")
RELIC = real("Relic", "{1}", "Artifact", "")
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
BLUE = real("Blue Bear", "{1}{U}", "Creature — Bear", "", "2", "2", colors=("U",))
TREEFOLK = Card(name="Treefolk", type_line="Token Creature — Treefolk", colors=("G",), power="3", toughness="4", oracle_text="Reach")


def table(*answers, battlefield=()):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield = list(battlefield)
    for seat in game.seats:
        seat.library = [FOREST] * 5
    return game, a, b, c


def offered(game, seat, prefix):
    return [x for x in game.legal_actions(seat) if x.startswith(prefix)]


def payable(game, seat, cost):
    return game._pay_cost(seat, cost_of(cost)) is not None


class StandardLandfallTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (NURSERY, CURATOR, PIT, ORIGINS, MADUIN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_sapling_nursery_costs_one_less_for_each_forest(self):
        game, a, _, _ = table(battlefield=lands(4, FOREST))
        a.hand = [NURSERY]
        self.assertEqual(offered(game, a, CAST + "Sapling Nursery"), [CAST + "Sapling Nursery"])
        a.battlefield = lands(4)  # four lands, none of them a Forest
        self.assertEqual(offered(game, a, CAST + "Sapling Nursery"), [])

    def test_sapling_nursery_makes_treefolk_and_forests_indestructible(self):
        treefolk, forest, bear = Permanent(TREEFOLK), Permanent(FOREST), Permanent(BEAR)
        nursery = Permanent(NURSERY)
        game, a, _, _ = table(battlefield=[nursery, treefolk, forest, bear] + lands(2))
        game._perform(a, offered(game, a, ACTIVATE + "Sapling Nursery")[0])
        run_stack(game)
        self.assertNotIn(nursery, a.battlefield)
        self.assertEqual([game.has_keyword(p, "indestructible") for p in (treefolk, forest, bear)], [True, True, False])

    def exile_with_curator(self, cards):
        curator = Permanent(CURATOR)
        game, a, b, _ = table(*[c.name for c in cards], battlefield=[curator] + lands(len(cards)))
        b.graveyard = list(cards)
        for _ in cards:
            game._perform(a, offered(game, a, ACTIVATE + "Keen-Eyed Curator")[0])
            run_stack(game)
        return game, curator, b

    def test_keen_eyed_curator_grows_with_four_card_types_exiled(self):
        game, curator, b = self.exile_with_curator([RELIC, BEAR, FOREST, SHOCK])
        self.assertEqual(b.graveyard, [])
        self.assertEqual((game.power(curator), game.toughness(curator)), (7, 7))
        self.assertTrue(game.has_keyword(curator, "trample"))

    def test_keen_eyed_curator_stays_small_with_three(self):
        game, curator, _ = self.exile_with_curator([RELIC, BEAR, FOREST])
        self.assertEqual(game.power(curator), 3)
        self.assertFalse(game.has_keyword(curator, "trample"))

    def test_keen_eyed_curator_counts_only_cards_still_in_exile(self):
        game, curator, b = self.exile_with_curator([RELIC, BEAR, FOREST, SHOCK])
        b.exile.remove(SHOCK)  # it left exile: a new object, no longer "exiled with" the Curator
        self.assertEqual(game.power(curator), 3)

    def test_pit_of_offerings_exiles_cards_and_taps_for_their_colors(self):
        game, a, b, _ = table("Blue Bear", "Shock", "No target")
        a.hand = [PIT]
        b.graveyard = [BLUE, SHOCK, BEAR]
        game._perform(a, PLAY_LAND + "Pit of Offerings")
        run_stack(game)
        pit = next(p for p in a.battlefield if p.card is PIT)
        self.assertEqual(([c.name for c in b.graveyard], pit.tapped), (["Bear"], True))
        pit.tapped = False
        self.assertEqual([payable(game, a, cost) for cost in ("{U}", "{R}", "{G}", "{C}")], [True, True, False, True])
        b.exile.remove(SHOCK)  # it left exile: its color is no longer one of the exiled cards' colors
        self.assertEqual([payable(game, a, cost) for cost in ("{U}", "{R}")], [True, False])

    def test_pit_of_offerings_with_nothing_exiled_makes_only_colorless(self):
        game, a, _, _ = table(battlefield=[Permanent(PIT)])
        self.assertEqual([payable(game, a, cost) for cost in ("{C}", "{G}")], [True, False])

    def test_esper_origins_cast_from_the_graveyard_comes_back_as_esper_maduin(self):
        game, a, _, _ = table(battlefield=lands(4) + [Permanent(BEAR)])
        a.graveyard, a.library = [ORIGINS], [BEAR, FOREST, FOREST]
        life = a.life
        game._perform(a, offered(game, a, "Cast from graveyard: Esper Origins")[0])
        run_stack(game)
        maduin = next(p for p in a.battlefield if p.card is MADUIN)
        self.assertEqual(maduin.counters, {"finality": 1, "lore": 1})
        self.assertEqual((a.life, a.graveyard, a.exile), (life + 2, [], []))
        self.assertEqual([c.name for c in a.hand], ["Bear"])  # chapter I: the top card was a permanent card

    def test_esper_origins_cast_from_the_hand_goes_to_the_graveyard(self):
        game, a, _, _ = table(battlefield=lands(2))
        a.hand = [ORIGINS]
        game._perform(a, CAST + "Esper Origins // Summon: Esper Maduin")
        run_stack(game)
        self.assertEqual(a.graveyard, [ORIGINS])
        self.assertFalse(any(p.card is MADUIN for p in a.battlefield))

    def test_esper_maduin_reveals_a_nonpermanent_card_and_leaves_it(self):
        game, a, _, _ = table()
        maduin = Permanent(MADUIN)
        a.battlefield, a.library, a.hand = [maduin], [SHOCK, FOREST], []
        game.trigger("chapter_1", maduin, a)
        run_stack(game)
        self.assertEqual((a.hand, a.library), ([], [SHOCK, FOREST]))

    def test_esper_maduin_pumps_the_other_creatures(self):
        game, a, _, _ = table()
        maduin, bear = Permanent(MADUIN), Permanent(BEAR)
        a.battlefield = [maduin, bear]
        game.trigger("chapter_3", maduin, a)
        run_stack(game)
        self.assertEqual((game.power(bear), game.has_keyword(bear, "trample")), (4, True))
        self.assertEqual((game.power(maduin), game.has_keyword(maduin, "trample")), (4, False))


if __name__ == "__main__":
    unittest.main()
