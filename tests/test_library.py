import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Draw, Mill, Scry, SearchForLands, Surveil, TargetMill, spell_effects, triggered_abilities
from infernal_machine.game import (CAST, KEEP_ON_TOP, LOOK_PROMPT, NONE_TAKEN, ORDER_TOP_PROMPT, PUT_IN_GRAVEYARD, SCRY_PROMPT, SEARCH_LAND_HAND_PROMPT,
                                   SEARCH_LAND_PROMPT, SURVEIL_PROMPT, Permanent)
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_effects import BEAR, BOLT, FOREST, lands, pick
from tests.test_exile import COMMANDER
from tests.test_mass_effects import table3
from tests.test_watch_triggers import COURSER

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
STEAM_VENTS = Card(name="Steam Vents", type_line="Land — Island Mountain", produced_mana=("U", "R"))
CULTIVATE = Card(name="Cultivate", mana_cost="{2}{G}", type_line="Sorcery",
                 oracle_text="Search your library for up to two basic land cards, reveal those cards, put one onto the "
                             "battlefield tapped and the other into your hand, then shuffle.")
FARSEEK = Card(name="Farseek", mana_cost="{1}{G}", type_line="Sorcery",
               oracle_text="Search your library for a Plains, Island, Swamp, or Mountain card, put it onto the "
                           "battlefield tapped, then shuffle.")
NATURES_LORE = Card(name="Nature's Lore", mana_cost="{1}{G}", type_line="Sorcery",
                    oracle_text="Search your library for a Forest card, put that card onto the battlefield, then shuffle.")
EXPLOSIVE = Card(name="Explosive Vegetation", mana_cost="{3}{G}", type_line="Sorcery",
                 oracle_text="Search your library for up to two basic land cards, put them onto the battlefield tapped, "
                             "then shuffle.")
OPT = REAL["Preordain"]
SURVEIL = REAL["Curate"]
MILL = REAL["Brain Freeze"]
DREDGE = Card(name="Glimpse", mana_cost="{U}", type_line="Sorcery", oracle_text="Mill three cards.")
TIDE = Card(name="Tide", mana_cost="{U}", type_line="Sorcery", oracle_text="Each opponent mills 2 cards.")
WIZARD = Card(name="Wizard", mana_cost="{U}", type_line="Creature — Wizard", power="1", toughness="1",
              oracle_text="When this creature enters, scry 2.")


def choices(*picks):
    """Answer each non-priority prompt with the next index from `picks` (and cast whatever is castable)."""
    remaining = iter(picks)
    cast = pick(CAST)

    def policy(prompt, options):
        if prompt.startswith("Priority"):
            return cast(prompt, options)
        return next(remaining, 0)
    return policy


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(CULTIVATE), [SearchForLands(2, (), 1, True, True)])
        self.assertEqual(spell_effects(FARSEEK), [SearchForLands(1, ("Plains", "Island", "Swamp", "Mountain"), 1, True, False)])
        self.assertEqual(spell_effects(NATURES_LORE), [SearchForLands(1, ("Forest",), 1, False, False)])
        self.assertEqual(spell_effects(EXPLOSIVE), [SearchForLands(2, (), 2, True, False)])
        self.assertEqual(spell_effects(OPT), [Scry(2), spell_effects(Card(name="d", oracle_text="Draw a card."))[0]])
        self.assertEqual(spell_effects(SURVEIL), [Surveil(2), Draw(1)])
        self.assertEqual(spell_effects(MILL)[0], TargetMill(3, "player"))
        self.assertEqual(spell_effects(DREDGE), [Mill(3, "you")])
        self.assertEqual(spell_effects(TIDE), [Mill(2, "each opponent")])
        self.assertEqual(spell_effects(Card(name="Blast", oracle_text="Scry X.")), [Scry("X")])
        self.assertEqual(triggered_abilities(WIZARD)[0].effects, (Scry(2),))

    def test_variants_that_need_more_are_unsupported(self):
        for text in ("Look at the top three cards of your library.",
                     "Search your library for up to three basic land cards, put them onto the battlefield."):
            self.assertIsNone(spell_effects(Card(name="Foo", oracle_text=text)), text)

    def test_report(self):
        for card in (CULTIVATE, FARSEEK, NATURES_LORE, EXPLOSIVE, OPT, SURVEIL, MILL, DREDGE, TIDE, WIZARD):
            self.assertEqual(unsupported_lines(card), [], card.name)


class LandRampTests(unittest.TestCase):
    def test_cultivate_one_land_to_the_battlefield_tapped_and_one_to_hand(self):
        game, players = table3(choices(0, 0))  # Forest to the battlefield; then the only option left, Island
        seat = game.seats[0]
        seat.hand = [CULTIVATE]
        seat.battlefield = lands(3)
        seat.library = [BOLT, FOREST, ISLAND, BEAR]
        game._priority_round(seat)
        entered = seat.battlefield[-1]
        self.assertEqual((entered.card, entered.tapped), (FOREST, True))
        self.assertEqual(seat.hand, [ISLAND])
        prompts = [(p, o) for p, o in players[0].prompts if p in (SEARCH_LAND_PROMPT, SEARCH_LAND_HAND_PROMPT)]
        self.assertEqual([p for p, _ in prompts], [SEARCH_LAND_PROMPT, SEARCH_LAND_HAND_PROMPT])
        self.assertEqual(prompts[1][1], ["Island"])  # the Forest is already taken
        revealed = [e for e in players[1].events if e["event"] == "revealed"]
        self.assertEqual([e["card"] for e in revealed], ["Island"])  # "reveal those cards"

    def test_only_one_basic_left_means_one_land_and_no_second_prompt(self):
        game, players = table3(choices())
        seat = game.seats[0]
        seat.hand = [CULTIVATE]
        seat.battlefield = lands(3)
        seat.library = [BOLT, FOREST]
        game._priority_round(seat)
        self.assertEqual((seat.battlefield[-1].card, seat.hand), (FOREST, []))
        self.assertFalse(any(p == SEARCH_LAND_HAND_PROMPT for p, _ in players[0].prompts))

    def test_no_basic_lands_just_shuffles(self):
        game, players = table3(choices())
        seat = game.seats[0]
        seat.hand = [CULTIVATE]
        seat.battlefield = lands(3)
        seat.library = [BOLT, BEAR]
        game._priority_round(seat)
        self.assertEqual(len(seat.battlefield), 3)
        self.assertIn({"event": "searched", "seat": 0, "found": False}, players[1].events)

    def test_fetching_triggers_landfall(self):
        game, _ = table3(choices(0, 0))
        seat = game.seats[0]
        seat.hand = [CULTIVATE]
        seat.battlefield = lands(3) + [Permanent(COURSER)]
        seat.library = [FOREST, ISLAND]
        game._priority_round(seat)
        self.assertEqual(seat.life, 41)  # once, for the land put onto the battlefield

    def test_land_types_include_nonbasic_lands(self):
        game, players = table3(choices())
        seat = game.seats[0]
        seat.hand = [FARSEEK]
        seat.battlefield = lands(2)
        seat.library = [FOREST, STEAM_VENTS, PLAINS, BOLT]
        game._priority_round(seat)
        options = next(o for p, o in players[0].prompts if p == SEARCH_LAND_PROMPT)
        self.assertEqual(sorted(options), ["Plains", "Steam Vents"])  # no Forest
        self.assertTrue(seat.battlefield[-1].tapped)

    def test_natures_lore_enters_untapped(self):
        game, _ = table3(choices())
        seat = game.seats[0]
        seat.hand = [NATURES_LORE]
        seat.battlefield = lands(2)
        seat.library = [ISLAND, FOREST]
        game._priority_round(seat)
        self.assertEqual((seat.battlefield[-1].card, seat.battlefield[-1].tapped), (FOREST, False))

    def test_two_lands_onto_the_battlefield(self):
        game, _ = table3(choices())
        seat = game.seats[0]
        seat.hand = [EXPLOSIVE]
        seat.battlefield = lands(4)
        seat.library = [FOREST, ISLAND, PLAINS]
        game._priority_round(seat)
        self.assertEqual([(p.card.name, p.tapped) for p in seat.battlefield[-2:]], [("Forest", True), ("Island", True)])
        self.assertEqual(len(seat.library), 1)


class ScryAndSurveilTests(unittest.TestCase):
    def test_scry_puts_chosen_cards_on_the_bottom(self):
        game, players = table3(choices(0, 1, 0))  # scry: keep the first, bottom the second; then draw
        seat = game.seats[0]
        seat.hand = [OPT]
        seat.battlefield = lands(1)
        seat.library = [BEAR, BOLT, FOREST, ISLAND]
        game._priority_round(seat)
        self.assertEqual(seat.hand, [BEAR])  # the kept card was on top and got drawn
        self.assertEqual([c.name for c in seat.library], ["Forest", "Island", "Lightning Bolt"])  # Bolt went to the bottom
        prompts = [p for p, _ in players[0].prompts if p.startswith(SCRY_PROMPT)]
        self.assertEqual(prompts, ["Scry: Grizzly Bears", "Scry: Lightning Bolt"])
        self.assertEqual(next(e for e in players[1].events if e["event"] == "scry"),
                         {"event": "scry", "seat": 0, "count": 2})  # others don't learn what was seen
        self.assertEqual(next(e for e in players[0].events if e["event"] == "scry")["bottom"], ["Lightning Bolt"])

    def test_scry_with_a_short_library(self):
        game, _ = table3(choices(1))
        seat = game.seats[0]
        seat.hand = [WIZARD]
        seat.battlefield = lands(1)
        seat.library = [BEAR]
        game._priority_round(seat)
        self.assertEqual(seat.library, [BEAR])  # scry 2 with one card: it went to the bottom, which is the same place

    def test_surveil_binning_is_public(self):
        game, players = table3(choices(1, 0))
        seat = game.seats[0]
        seat.hand = [SURVEIL]
        seat.battlefield = lands(2)
        seat.library = [BOLT, BEAR, FOREST]
        game._priority_round(seat)
        self.assertEqual(([c.name for c in seat.library], [c.name for c in seat.graveyard][:1]),
                         (["Forest"], ["Lightning Bolt"]))  # the Bear stayed on top, then Curate drew it
        event = next(e for e in players[2].events if e["event"] == "surveil")
        self.assertEqual(event["graveyard"], ["Lightning Bolt"])
        options = next(o for p, o in players[0].prompts if p.startswith(SURVEIL_PROMPT))
        self.assertEqual(options, [KEEP_ON_TOP, PUT_IN_GRAVEYARD])


class MillTests(unittest.TestCase):
    def test_target_opponent_mills(self):
        game, players = table3(pick(CAST, "Player: B"))
        seat = game.seats[0]
        seat.hand = [MILL]
        seat.battlefield = lands(2)
        game.seats[1].library = [BEAR, BOLT, FOREST, ISLAND]
        game._priority_round(seat)
        self.assertEqual([c.name for c in game.seats[1].graveyard], ["Grizzly Bears", "Lightning Bolt", "Forest"])
        self.assertEqual(len(game.seats[1].library), 1)
        self.assertEqual(next(e for e in players[2].events if e["event"] == "milled")["cards"],
                         ["Grizzly Bears", "Lightning Bolt", "Forest"])

    def test_mill_yourself_and_each_opponent(self):
        game, _ = table3(pick(CAST))
        seat = game.seats[0]
        seat.hand = [DREDGE, TIDE]
        seat.battlefield = lands(2)
        for s in game.seats:
            s.library = [FOREST] * 6
        game._priority_round(seat)
        self.assertEqual([len(s.graveyard) for s in game.seats], [3 + 2, 2, 2])  # seat 0: 3 milled plus the two spells; the others: 2 milled

    def test_milling_more_than_the_library_is_not_a_loss_yet(self):
        game, _ = table3(pick(CAST, "Player: B"))
        seat = game.seats[0]
        seat.hand = [MILL]
        seat.battlefield = lands(2)
        game.seats[1].library = [FOREST]
        game._priority_round(seat)
        self.assertEqual((len(game.seats[1].graveyard), game.seats[1].lost), (1, False))
        game.draw(game.seats[1], 1)
        game._check_state()
        self.assertTrue(game.seats[1].lost)

    def test_milled_commander_is_not_an_issue(self):
        game, _ = table3()
        game.seats[1].commander_names = {"Omnath"}
        game.seats[1].library = [COMMANDER]
        game.seats[1].player.policy = pick("Command zone")
        game.mill(game.seats[1], 1)
        self.assertEqual(game.seats[1].command_zone, [COMMANDER])  # may return to the command zone


if __name__ == "__main__":
    unittest.main()


IMPULSE = Card(name="Impulse", mana_cost="{1}{U}", type_line="Instant",
               oracle_text="Look at the top four cards of your library. Put one of them into your hand and the rest on "
                           "the bottom of your library in any order.")
DIG = Card(name="Dig", mana_cost="{2}{G}", type_line="Sorcery",
           oracle_text="Look at the top five cards of your library. You may reveal a creature card from among them and "
                       "put it into your hand. Put the rest on the bottom of your library in a random order.")


class ReorderAndImpulseTests(unittest.TestCase):
    def test_scry_lets_you_order_the_cards_you_keep(self):
        game, players = table3(choices(0, 0, 1))  # keep both; then the second of the two goes on top
        seat = game.seats[0]
        seat.hand = [WIZARD]
        seat.battlefield = lands(1)
        seat.library = [BEAR, BOLT, FOREST]
        game._priority_round(seat)
        self.assertEqual([c.name for c in seat.library], ["Lightning Bolt", "Grizzly Bears", "Forest"])
        options = next(o for p, o in players[0].prompts if p == ORDER_TOP_PROMPT)
        self.assertEqual(options, ["Grizzly Bears", "Lightning Bolt"])

    def test_no_order_question_for_a_single_card(self):
        game, players = table3(choices(0, 1))
        seat = game.seats[0]
        seat.hand = [WIZARD]
        seat.battlefield = lands(1)
        seat.library = [BEAR, BOLT, FOREST]
        game._priority_round(seat)
        self.assertFalse([p for p, _ in players[0].prompts if p == ORDER_TOP_PROMPT])

    def test_surveil_orders_what_stays(self):
        game, _ = table3(choices(0, 0, 1))
        seat = game.seats[0]
        seat.hand = [SURVEIL]
        seat.battlefield = lands(2)
        seat.library = [BOLT, BEAR, FOREST]
        game._priority_round(seat)
        self.assertEqual([c.name for c in seat.library], ["Lightning Bolt", "Forest"])  # Bear, Bolt in that order; Curate drew the Bear

    def test_look_at_four_takes_one_and_bottoms_the_rest(self):
        game, players = table3(choices(1))
        seat = game.seats[0]
        seat.hand = [IMPULSE]
        seat.battlefield = lands(2)
        seat.library = [BEAR, BOLT, FOREST, ISLAND, PLAINS]
        game._priority_round(seat)
        self.assertEqual([c.name for c in seat.hand], ["Lightning Bolt"])
        self.assertEqual(sorted(c.name for c in seat.library[-3:]), ["Forest", "Grizzly Bears", "Island"])
        self.assertEqual(seat.library[0].name, "Plains")
        options = next(o for p, o in players[0].prompts if p == LOOK_PROMPT)
        self.assertEqual(options, ["Grizzly Bears", "Lightning Bolt", "Forest", "Island"])  # only the top four
        self.assertNotIn("card", next(e for e in players[1].events if e["event"] == "looked"))

    def test_optional_reveal_takes_a_creature_and_shows_it(self):
        game, players = table3(choices(0))
        seat = game.seats[0]
        seat.hand = [DIG]
        seat.battlefield = lands(3)
        seat.library = [BOLT, BEAR, FOREST, ISLAND, PLAINS, ISLAND]
        game._priority_round(seat)
        self.assertEqual([c.name for c in seat.hand], ["Grizzly Bears"])
        options = next(o for p, o in players[0].prompts if p == LOOK_PROMPT)
        self.assertEqual(options, ["Grizzly Bears", NONE_TAKEN])  # Bolt and the lands aren't creatures
        self.assertEqual(next(e for e in players[2].events if e["event"] == "looked")["card"], "Grizzly Bears")
        self.assertEqual(len(seat.library), 5)

    def test_optional_reveal_can_take_nothing(self):
        game, _ = table3(choices(1))
        seat = game.seats[0]
        seat.hand = [DIG]
        seat.battlefield = lands(3)
        seat.library = [BOLT, BEAR, FOREST, ISLAND, PLAINS, ISLAND]
        game._priority_round(seat)
        self.assertEqual(seat.hand, [])
        self.assertEqual(len(seat.library), 6)

    def test_no_creature_among_them_asks_nothing(self):
        game, players = table3(choices())
        seat = game.seats[0]
        seat.hand = [DIG]
        seat.battlefield = lands(3)
        seat.library = [BOLT, FOREST, ISLAND, PLAINS, ISLAND, BEAR]
        game._priority_round(seat)
        self.assertFalse([p for p, _ in players[0].prompts if p == LOOK_PROMPT])
        self.assertEqual(len(seat.library), 6)

    def test_a_short_library_is_fine(self):
        game, _ = table3(choices(0))
        seat = game.seats[0]
        seat.hand = [IMPULSE]
        seat.battlefield = lands(2)
        seat.library = [BEAR]
        game._priority_round(seat)
        self.assertEqual([c.name for c in seat.hand], ["Grizzly Bears"])
        self.assertEqual(seat.library, [])

    def test_half_a_look_is_not_understood(self):
        look = Card(name="Peek", mana_cost="{U}", type_line="Sorcery", oracle_text="Look at the top three cards of your library.")
        reveal = Card(name="Half", mana_cost="{U}", type_line="Sorcery",
                      oracle_text="Look at the top five cards of your library. You may reveal a creature card from among them and put it into your hand.")
        self.assertIsNone(spell_effects(look))
        self.assertIsNone(spell_effects(reveal))
        self.assertEqual(unsupported_lines(IMPULSE) + unsupported_lines(DIG), [])
