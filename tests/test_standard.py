"""The Standard game: 60-card decks, 20 life, four copies, no commander (#354)."""

import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, CardNotFound, Deck
from infernal_machine.formats import COMMANDER, FORMATS, STANDARD, deck_problems, format_of
from infernal_machine.game import STARTING_LIFE, Game
from infernal_machine.matchup import matchups
from infernal_machine.server import DeckRejected, load_human_deck

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
OGRE = Card(name="Hill Giant", mana_cost="{3}{G}", cmc=4, type_line="Creature — Giant", power="3", toughness="3")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
RATS = Card(name="Relentless Rats", mana_cost="{1}{B}", cmc=2, type_line="Creature — Rat", power="2", toughness="2",
            oracle_text="Relentless Rats gets +1/+1 for each other creature you control named Relentless Rats.\n"
                        "A deck can have any number of cards named Relentless Rats.")
ROTATED = Card(name="Old Card", mana_cost="{G}", cmc=1, type_line="Creature — Elf", power="1", toughness="1", legal=("commander",))
SOURCE_DATA = {"name": "Llanowar Visionary", "mana_cost": "{2}{G}", "cmc": 3, "type_line": "Creature — Elf Druid", "oracle_text": "",
               "legalities": {"standard": "legal", "commander": "legal"}}


def standard(*, main=None, sideboard=()):
    return Deck(commanders=[], main=main if main is not None else [FOREST] * 24 + [BEAR] * 4 + [RATS] * 32, sideboard=list(sideboard))


PLAYABLE = standard(main=[FOREST] * 24 + [BEAR] * 18 + [OGRE] * 18)  # not a legal deck (18 copies), but one the bots can play


class FakeSource:
    def __init__(self, *cards):
        self.cards = {c.name: c for c in cards}

    def get(self, name):
        if name not in self.cards:
            raise CardNotFound(name)
        return self.cards[name]

    def get_many(self, names):
        return {n: self.get(n) for n in dict.fromkeys(names)}


class LegalityTests(unittest.TestCase):
    def problems(self, deck):
        return deck_problems(deck, STANDARD)

    def test_a_sixty_card_deck_with_four_copies_is_legal(self):
        self.assertEqual(self.problems(standard(main=[FOREST] * 24 + [BEAR] * 4 + [OGRE] * 4 + [RATS] * 28)), [])

    def test_too_few_cards(self):
        self.assertEqual(self.problems(standard(main=[FOREST] * 59)), ["Main deck has 59 cards; needs at least 60"])

    def test_more_than_sixty_is_fine(self):
        self.assertEqual(self.problems(standard(main=[FOREST] * 70)), [])

    def test_a_fifth_copy_is_not(self):
        problems = self.problems(standard(main=[FOREST] * 24 + [BEAR] * 5 + [OGRE] * 4 + [RATS] * 27))
        self.assertEqual(problems, ["Grizzly Bears: 5 copies, limit is 4"])

    def test_the_sideboard_counts_toward_the_limit(self):
        main = [FOREST] * 24 + [BEAR] * 4 + [OGRE] * 4 + [RATS] * 28
        self.assertEqual(self.problems(standard(main=main, sideboard=[BEAR])), ["Grizzly Bears: 5 copies, limit is 4"])

    def test_sideboard_size(self):
        self.assertEqual(self.problems(standard(sideboard=[RATS] * 15)), [])
        self.assertEqual(self.problems(standard(sideboard=[RATS] * 16)), ["Sideboard has 16 cards; the limit is 15"])

    def test_basic_lands_and_any_number_cards_are_unlimited(self):
        self.assertEqual(self.problems(standard(main=[FOREST] * 30 + [RATS] * 30)), [])

    def test_a_card_that_is_not_standard_legal(self):
        self.assertEqual(self.problems(standard(main=[FOREST] * 59 + [ROTATED])), ["Old Card is not legal in Standard"])

    def test_a_commander_has_no_place_in_standard(self):
        deck = Deck(commanders=[BOSS], main=[FOREST] * 60, sideboard=[])
        self.assertEqual(self.problems(deck), ["Standard decks have no commander"])

    def test_commander_rules_are_unchanged(self):
        deck = Deck(commanders=[BOSS], main=[FOREST] * 99, sideboard=[])
        self.assertEqual(deck_problems(deck, COMMANDER), [])
        self.assertTrue(deck_problems(standard(), COMMANDER))  # 60 cards and no commander is not a Commander deck

    def test_scryfall_legality_is_read(self):
        card = Card.from_scryfall(SOURCE_DATA)
        self.assertTrue(card.legal_in("standard") and card.legal_in("commander"))
        rotated = Card.from_scryfall({**SOURCE_DATA, "legalities": {"standard": "not_legal", "commander": "legal"}})
        self.assertFalse(rotated.legal_in("standard"))
        self.assertTrue(rotated.legal_in("commander"))
        banned = Card.from_scryfall({**SOURCE_DATA, "legalities": {"standard": "banned", "commander": "legal"}})
        self.assertFalse(banned.legal_in("standard"), "Standard's ban list is Scryfall's legality: a banned card is not legal (#521)")
        self.assertEqual(deck_problems(standard(main=[FOREST] * 59 + [banned]), STANDARD), [f"{banned.name} is not legal in Standard"])
        self.assertEqual(Card.from_dict(card.to_dict()).legal_in("standard"), True)  # it survives the card cache
        self.assertEqual(Card.from_dict(rotated.to_dict()).legal_in("standard"), False)


class FormatTests(unittest.TestCase):
    def test_the_formats(self):
        self.assertEqual((COMMANDER.life, STANDARD.life, STANDARD.copy_limit), (40, 20, 4))
        self.assertEqual(set(FORMATS), {"commander", "standard", "brawl", "duel", "oathbreaker", "pioneer", "modern", "legacy", "vintage", "pauper"})

    def test_a_table_is_the_format_its_decks_are(self):
        commander = Deck([BOSS], [FOREST] * 99, [])
        self.assertIs(format_of([commander, commander]), COMMANDER)
        self.assertIs(format_of([standard(), standard()]), STANDARD)
        with self.assertRaises(ValueError):
            format_of([commander, standard()])


class GameTests(unittest.TestCase):
    def test_standard_starts_at_twenty_life_and_commander_at_forty(self):
        deck = PLAYABLE
        game = Game([(BotPlayer("A", deck), deck), (BotPlayer("B", deck), deck)], seed=1, format=STANDARD)
        self.assertEqual([s.life for s in game.seats], [20, 20])
        self.assertEqual([s.command_zone for s in game.seats], [[], []])
        commander = Deck([BOSS], [FOREST] * 99, [])
        pair = [(BotPlayer("A", commander), commander), (BotPlayer("B", commander), commander)]
        self.assertEqual([s.life for s in Game(pair, seed=1).seats], [STARTING_LIFE] * 2)

    def test_a_two_player_standard_game_has_no_free_mulligan_and_the_first_player_skips_a_draw(self):
        deck = PLAYABLE
        game = Game([(BotPlayer("A", deck), deck), (BotPlayer("B", deck), deck)], seed=3, format=STANDARD)
        events, forward = [], game.broadcast

        def tap(event, skip=None):
            events.append(event)
            forward(event, skip)

        game.broadcast = tap  # type: ignore[method-assign]
        game.play(max_turns=2)  # the starting player's turn, then the other player's
        self.assertFalse(game.multiplayer)
        draws = [e["seat"] for e in events if e["event"] == "drew"]
        self.assertEqual(draws, [1 - game.starting_seat])  # CR 103.8a: only the second player drew a card on turn one

    def test_bots_play_a_standard_game_to_the_end(self):
        deck = PLAYABLE
        game = Game([(BotPlayer("A", deck), deck), (BotPlayer("B", deck), deck)], seed=5, format=STANDARD)
        winner = game.play(max_turns=80)
        self.assertTrue(all(s.life <= 20 for s in game.seats))
        self.assertTrue(winner is not None or game.turn >= 80)

    def test_matchups_infer_standard_from_decks_without_commanders(self):
        records = matchups(PLAYABLE, {"mirror": PLAYABLE}, games=2, max_turns=20)
        self.assertEqual((records[0].games, records[0].errors), (2, 0))


class ServerTests(unittest.TestCase):
    def test_a_standard_table_checks_standard_decks(self):
        source = FakeSource(FOREST, RATS)
        legal = {"deck": "24 Forest\n36 Relentless Rats"}
        self.assertEqual(len(load_human_deck(legal, source, True, STANDARD).main), 60)
        with self.assertRaises(DeckRejected) as rejected:
            load_human_deck({"deck": "24 Forest\n12 Relentless Rats"}, source, True, STANDARD)
        self.assertIn("needs at least 60", str(rejected.exception))
        with self.assertRaises(DeckRejected):  # the same 60 cards are not a Commander deck
            load_human_deck(legal, source, True, COMMANDER)


if __name__ == "__main__":
    unittest.main()
