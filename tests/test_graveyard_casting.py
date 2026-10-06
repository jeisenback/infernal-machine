import unittest

from infernal_machine.bot import _cast_name
from infernal_machine.cards import Card
from infernal_machine.effects import GraveyardCast, graveyard_casts
from infernal_machine.game import CAST, CAST_GRAVEYARD, ESCAPE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick, table

SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
FLASH = Card(name="Spell", mana_cost="{1}", type_line="Sorcery", oracle_text="You gain 3 life.\nFlashback {3}")
BOLT = Card(name="Quick Spell", mana_cost="{1}", type_line="Instant", oracle_text="You gain 3 life.\nFlashback {3}")
ESCAPER = Card(name="Escaper", mana_cost="{3}{B}", type_line="Creature — Test", power="2", toughness="2", cmc=4.0,
               oracle_text="Escape—{1}{B}, Exile two other cards from your graveyard.")
FODDER_A = Card(name="Fodder A", type_line="Creature — Test", power="1", toughness="1")
FODDER_B = Card(name="Fodder B", type_line="Creature — Test", power="1", toughness="1")


def setup(graveyard, battlefield, policy=None, hand=()):
    game, player, _ = table(policy or pick(CAST_GRAVEYARD))
    seat = game.seats[0]
    seat.graveyard = list(graveyard)
    seat.battlefield = battlefield
    seat.hand = list(hand)
    return game, seat, player


class ParseTests(unittest.TestCase):
    def test_flashback(self):
        self.assertEqual(graveyard_casts(FLASH), [GraveyardCast("Flashback", "{3}", exile_after=True)])

    def test_escape(self):
        self.assertEqual(graveyard_casts(ESCAPER), [GraveyardCast("Escape", "{1}{B}", exile=2)])
        five = Card(name="x", oracle_text="Escape—{4}{B}{B}, Exile five other cards from your graveyard.")
        self.assertEqual(graveyard_casts(five)[0].exile, 5)

    def test_plain_cards_have_none(self):
        self.assertEqual(graveyard_casts(Card(name="x", oracle_text="You gain 3 life.")), [])

    def test_the_report_counts_them_as_playable(self):
        for card in (FLASH, BOLT, ESCAPER):
            self.assertEqual(unsupported_lines(card), [], card.name)


class FlashbackTests(unittest.TestCase):
    def test_offered_only_when_the_flashback_cost_is_affordable(self):
        game, seat, _ = setup([FLASH], lands(2))
        self.assertNotIn(CAST_GRAVEYARD + "Spell", game.legal_actions(seat))
        seat.battlefield = lands(3)
        self.assertIn(CAST_GRAVEYARD + "Spell", game.legal_actions(seat))

    def test_it_pays_the_flashback_cost_not_the_mana_cost(self):
        game, seat, _ = setup([FLASH], lands(3))
        game._priority_round(seat)
        self.assertEqual(sum(p.tapped for p in seat.battlefield), 3)

    def test_it_is_exiled_afterwards(self):
        game, seat, _ = setup([FLASH], lands(3))
        game._priority_round(seat)
        self.assertEqual(seat.life, 43)
        self.assertEqual((seat.graveyard, [c.name for c in seat.exile]), ([], ["Spell"]))

    def test_cast_from_hand_then_flashed_back(self):
        game, seat, _ = setup([], lands(5), pick(CAST_GRAVEYARD, CAST), hand=[FLASH])
        game._priority_round(seat)
        self.assertEqual(seat.life, 46)
        self.assertEqual(([c.name for c in seat.graveyard], [c.name for c in seat.exile]), ([], ["Spell"]))

    def test_a_countered_flashback_spell_is_exiled(self):
        game, seat, _ = setup([FLASH], lands(3))
        game._cast(seat, FLASH, seat.graveyard, graveyard=graveyard_casts(FLASH)[0])
        game.counter(game.stack[0])
        self.assertEqual((seat.graveyard, [c.name for c in seat.exile]), ([], ["Spell"]))

    def test_a_sorcery_waits_for_sorcery_timing(self):
        game, seat, _ = setup([FLASH, BOLT], lands(3))
        game.step = "end"
        offered = game.legal_actions(seat)
        self.assertNotIn(CAST_GRAVEYARD + "Spell", offered)
        self.assertIn(CAST_GRAVEYARD + "Quick Spell", offered)

    def test_the_event_says_where_it_came_from(self):
        game, seat, player = setup([FLASH], lands(3))
        game._priority_round(seat)
        cast = next(e for e in player.events if e["event"] == "cast")
        self.assertEqual(cast["from"], "graveyard")


class EscapeTests(unittest.TestCase):
    def test_it_needs_enough_other_cards(self):
        game, seat, _ = setup([ESCAPER, FODDER_A], lands(2, SWAMP))
        self.assertNotIn(CAST_GRAVEYARD + "Escaper", game.legal_actions(seat))
        seat.graveyard.append(FODDER_B)
        self.assertIn(CAST_GRAVEYARD + "Escaper", game.legal_actions(seat))

    def test_it_exiles_the_other_cards_and_stays_on_the_battlefield(self):
        game, seat, player = setup([ESCAPER, FODDER_A, FODDER_B], lands(2, SWAMP))
        game._priority_round(seat)
        self.assertIn("Escaper", [p.card.name for p in seat.battlefield])
        self.assertEqual((seat.graveyard, sorted(c.name for c in seat.exile)), ([], ["Fodder A", "Fodder B"]))
        self.assertEqual(len([1 for prompt, _ in player.prompts if prompt == ESCAPE_PROMPT]), 2)

    def test_it_counts_as_cards_leaving_the_graveyard(self):
        game, seat, _ = setup([ESCAPER, FODDER_A, FODDER_B], lands(2, SWAMP))
        game._priority_round(seat)
        self.assertEqual(seat.graveyard_left_turn, game.turn)

    def test_it_needs_the_mana(self):
        game, seat, _ = setup([ESCAPER, FODDER_A, FODDER_B], lands(1, SWAMP))
        self.assertNotIn(CAST_GRAVEYARD + "Escaper", game.legal_actions(seat))


class BotTests(unittest.TestCase):
    def test_the_card_name_from_either_kind_of_cast(self):
        self.assertEqual(_cast_name(CAST + "Spell"), "Spell")
        self.assertEqual(_cast_name(CAST_GRAVEYARD + "Spell"), "Spell")


if __name__ == "__main__":
    unittest.main()
