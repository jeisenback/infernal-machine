import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import ReturnAllToHand, ReturnFromGraveyard, SearchForLands, SearchLibrary, spell_effects
from infernal_machine.game import CAST, SEARCH_CARD_PROMPT, SEARCH_LAND_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import FOREST, lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
SHRINE = Card(name="Shrine", type_line="Legendary Land")
VERGE = Card(name="Verge", type_line="Land — Forest Island", produced_mana=("G", "U"))
KING = Card(name="King", mana_cost="{3}", type_line="Legendary Creature — Elf", power="3", toughness="3")
COMMONER = Card(name="Commoner", mana_cost="{1}", type_line="Creature — Elf", power="1", toughness="1")
LEGEND_ARTIFACT = Card(name="Relic", mana_cost="{2}", type_line="Legendary Artifact")
BLADE = Card(name="Blade", mana_cost="{2}", type_line="Artifact — Equipment", cmc=2.0)
BIG_BLADE = Card(name="Big Blade", mana_cost="{5}", type_line="Artifact — Equipment", cmc=5.0)
BLESSING = Card(name="Blessing", mana_cost="{1}", type_line="Enchantment — Aura", cmc=1.0)


def sorcery(name, text):
    return Card(name=name, mana_cost="{U}", type_line="Sorcery", oracle_text=text)


def options_of(players, prompt):
    return next(o for p, o in players[0].prompts if p == prompt)


class ParseTests(unittest.TestCase):
    def test_tutors_by_supertype_and_subtype(self):
        for text, kind in (("a legendary creature card", "legendary creature"), ("a legendary card", "legendary"),
                           ("an Aura card", "aura"), ("an Equipment card with mana value 2 or less", "equipment|mv<=2")):
            card = sorcery("Tutor", f"Search your library for {text}, reveal it, put it into your hand, then shuffle.")
            self.assertEqual(spell_effects(card), [SearchLibrary(kind, "hand", True)], text)
            self.assertEqual(unsupported_lines(card), [])

    def test_land_searches(self):
        self.assertEqual(spell_effects(sorcery("Nonbasic", "Search your library for a nonbasic land card, put it onto the "
                                                           "battlefield, then shuffle.")),
                         [SearchForLands(1, ("nonbasic",), 1, False, False)])
        self.assertEqual(spell_effects(sorcery("Claim", "Search your library for up to two Forest cards, put them onto the "
                                                        "battlefield, then shuffle.")),
                         [SearchForLands(2, ("Forest",), 2, False, False)])
        self.assertEqual(spell_effects(sorcery("Claim", "Search your library for up to two Mountain or Forest cards, put them "
                                                        "onto the battlefield tapped, then shuffle.")),
                         [SearchForLands(2, ("Mountain", "Forest"), 2, True, False)])

    def test_reanimating_tapped(self):
        self.assertEqual(spell_effects(sorcery("Raise", "Return target creature card from your graveyard to the battlefield "
                                                        "tapped.")),
                         [ReturnFromGraveyard("graveyard:creature:yours", "battlefield", True)])

    def test_your_opponents_control(self):
        self.assertEqual(spell_effects(sorcery("Tide", "Return all creatures your opponents control to their owners' hands.")),
                         [ReturnAllToHand("creature an opponent controls")])
        self.assertEqual(unsupported_lines(sorcery("Wrath", "Destroy all creatures your opponents control.")), [])


class TutorTests(unittest.TestCase):
    def search(self, text, library):
        game, players = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [sorcery("Tutor", text)], lands(1), list(library)
        game._priority_round(a)
        return game, a, players

    def test_legendary_creature_only(self):
        game, a, players = self.search("Search your library for a legendary creature card, reveal it, put it into your hand, "
                                       "then shuffle.", [COMMONER, KING, LEGEND_ARTIFACT, BEAR])
        self.assertEqual(options_of(players, SEARCH_CARD_PROMPT), ["King"])
        self.assertEqual([c.name for c in a.hand], ["King"])

    def test_legendary_of_any_type(self):
        game, a, players = self.search("Search your library for a legendary card, reveal it, put it into your hand, then "
                                       "shuffle.", [COMMONER, KING, LEGEND_ARTIFACT])
        self.assertEqual(options_of(players, SEARCH_CARD_PROMPT), ["King", "Relic"])

    def test_nonbasic_land_card_to_hand(self):
        game, a, players = self.search("Search your library for a nonbasic land card, reveal it, put it into your hand, then "
                                       "shuffle.", [FOREST, SHRINE, VERGE])
        self.assertEqual(options_of(players, SEARCH_CARD_PROMPT), ["Shrine", "Verge"])

    def test_aura_and_equipment_with_a_mana_value_limit(self):
        game, a, players = self.search("Search your library for an Equipment card with mana value 3 or less, reveal it, put it "
                                       "into your hand, then shuffle.", [BIG_BLADE, BLADE, BLESSING])
        self.assertEqual(options_of(players, SEARCH_CARD_PROMPT), ["Blade"])
        game, a, players = self.search("Search your library for an Aura card, reveal it, put it into your hand, then shuffle.",
                                       [BIG_BLADE, BLADE, BLESSING])
        self.assertEqual(options_of(players, SEARCH_CARD_PROMPT), ["Blessing"])


class LandSearchTests(unittest.TestCase):
    def search(self, text, library):
        game, players = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [sorcery("Fetch", text)], lands(1), list(library)
        game._priority_round(a)
        return game, a, players

    def test_nonbasic_only(self):
        game, a, players = self.search("Search your library for a nonbasic land card, put it onto the battlefield, then shuffle.",
                                       [FOREST, MOUNTAIN, SHRINE, VERGE])
        self.assertEqual(options_of(players, SEARCH_LAND_PROMPT), ["Shrine", "Verge"])
        self.assertEqual(a.battlefield[-1].card.name, "Shrine")

    def test_two_of_a_land_type_untapped_or_tapped(self):
        game, a, _ = self.search("Search your library for up to two Forest cards, put them onto the battlefield, then shuffle.",
                                 [FOREST, FOREST, MOUNTAIN, FOREST])
        found = [p for p in a.battlefield if p.card.name == "Forest"]
        self.assertEqual((len(found), [p.tapped for p in found], len(a.library)), (2, [False, False], 2))
        game, a, _ = self.search("Search your library for up to two Forest cards, put them onto the battlefield tapped, then "
                                 "shuffle.", [FOREST, FOREST, MOUNTAIN])
        self.assertEqual([p.tapped for p in a.battlefield if p.card.name == "Forest"], [True, True])

    def test_a_dual_land_counts_as_either_type(self):
        game, a, players = self.search("Search your library for up to two Forest cards, put them onto the battlefield, then "
                                       "shuffle.", [VERGE, FOREST])
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name in ("Verge", "Forest")), ["Forest", "Verge"])


class RecursionTests(unittest.TestCase):
    def test_reanimating_tapped(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand = [sorcery("Raise", "Return target creature card from your graveyard to the battlefield tapped.")]
        a.battlefield, a.graveyard = lands(1), [OGRE]
        game._priority_round(a)
        ogre = next(p for p in a.battlefield if p.card.name == "Ogre")
        self.assertTrue(ogre.tapped and ogre.sick)

    def test_reanimating_untapped_stays_untapped(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand = [sorcery("Raise", "Return target creature card from your graveyard to the battlefield.")]
        a.battlefield, a.graveyard = lands(1), [OGRE]
        game._priority_round(a)
        self.assertFalse(next(p for p in a.battlefield if p.card.name == "Ogre").tapped)

    def test_legendary_creatures_only_are_offered(self):
        game, players = table3(pick(CAST))
        a = game.seats[0]
        a.hand = [sorcery("Raise", "Return target legendary creature card from your graveyard to your hand.")]
        a.battlefield, a.graveyard = lands(1), [COMMONER, KING]
        game._priority_round(a)
        self.assertEqual(options_of(players, "Choose a target for Raise"), ["King (seat 0 graveyard)"])
        self.assertEqual([c.name for c in a.hand], ["King"])


class OpponentsMassTests(unittest.TestCase):
    def cast(self, text):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        a.hand, a.battlefield = [sorcery("Sweep", text)], lands(1) + [Permanent(BEAR)]
        b.battlefield, c.battlefield = [Permanent(OGRE)], [Permanent(BEAR), Permanent(FOREST)]
        game._priority_round(a)
        return game

    def test_bounce_only_opponents_creatures(self):
        game = self.cast("Return all creatures your opponents control to their owners' hands.")
        a, b, c = game.seats
        self.assertEqual(([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], b.battlefield,
                          [x.name for x in b.hand], [p.card.name for p in c.battlefield], [x.name for x in c.hand]),
                         (["Bear"], [], ["Ogre"], ["Forest"], ["Bear"]))

    def test_destroy_only_opponents_creatures(self):
        game = self.cast("Destroy all creatures your opponents control.")
        a, b, c = game.seats
        self.assertEqual(([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], b.battlefield,
                          [p.card.name for p in c.battlefield]), (["Bear"], [], ["Forest"]))
