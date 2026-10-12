import unittest

from infernal_machine.bot import BotPlayer, goldfish, keep_hand, worst_card
from infernal_machine.cards import Card, Deck
from infernal_machine.game import (CAST, CYCLE, DONE_MODES, KEEP_ON_TOP, MODE_PROMPT, PASS, PUT_IN_GRAVEYARD, PUT_ON_BOTTOM,
                                   SCRY_PROMPT, SURVEIL_PROMPT, Game)

LAND = Card(name="Wastes", type_line="Basic Land")
CHEAP = Card(name="Sol Ring", type_line="Artifact", cmc=1)
PRICEY = Card(name="Ulamog", type_line="Legendary Creature — Eldrazi", cmc=10)
COMMANDER = Card(name="Commander", type_line="Legendary Creature — Golem")


def deck(lands, spells):
    return Deck(commanders=[COMMANDER], main=[LAND] * lands + [CHEAP] * spells, sideboard=[])


class KeepTests(unittest.TestCase):
    def test_keeps_two_to_five_lands(self):
        self.assertFalse(keep_hand([LAND] + [CHEAP] * 6))
        self.assertTrue(keep_hand([LAND] * 2 + [CHEAP] * 5))
        self.assertTrue(keep_hand([LAND] * 5 + [CHEAP] * 2))
        self.assertFalse(keep_hand([LAND] * 6 + [CHEAP]))

    def test_keeps_anything_after_two_mulligans(self):
        self.assertTrue(keep_hand([CHEAP] * 7, mulligans=2))

    def test_worst_card(self):
        self.assertEqual(worst_card([LAND, CHEAP, PRICEY, CHEAP]), 2)
        self.assertEqual(worst_card([LAND, LAND, LAND, PRICEY]), 0)
        self.assertEqual(worst_card([LAND]), 0)


class BotPlayerTests(unittest.TestCase):
    def test_bots_play_a_game(self):
        # Land-heavy so no land drop is ever missed; the bots still mulligan 6+ land hands.
        a, b = BotPlayer("A", deck(90, 9)), BotPlayer("B", deck(90, 9))
        game = Game([(a, deck(90, 9)), (b, deck(90, 9))], seed=9)
        game.play(max_turns=6)
        for seat in game.seats:
            self.assertEqual(len(seat.battlefield), 3)  # one land per own turn
            self.assertLessEqual(len(seat.hand), 7)


    def test_bots_cast_spells(self):
        forest = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
        bear = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear")
        commander = Card(name="Omnath", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elemental")
        green = Deck(commanders=[commander], main=[forest] * 40 + [bear] * 59, sideboard=[])
        a, b = BotPlayer("A", green), BotPlayer("B", green)
        game = Game([(a, green), (b, green)], seed=3)
        game.play(max_turns=10)
        for seat in game.seats:
            names = [p.card.name for p in seat.battlefield]
            self.assertIn("Grizzly Bears", names)
            self.assertIn("Omnath", names)  # cast from the command zone once it had four lands


    def test_bots_use_spell_effects(self):
        from tests.test_effects import BEAR, BOLT, COUNTERSPELL, DIVINATION, MURDER, RAINBOW
        commander = Card(name="Omnath", mana_cost="{2}{G}", type_line="Legendary Creature — Elemental", toughness="3")
        mixed = Deck([commander], [RAINBOW] * 38 + [BOLT] * 20 + [DIVINATION, COUNTERSPELL, MURDER] * 7 + [BEAR] * 20, [])
        bots = [BotPlayer(f"P{i}", mixed) for i in range(3)]
        game = Game([(b, mixed) for b in bots], seed=4)
        game.play(max_turns=30)
        self.assertTrue(any(seat.life < 40 for seat in game.seats))
        self.assertTrue(any(BOLT in seat.graveyard for seat in game.seats))


WRATH = Card(name="Wrath of God", mana_cost="{2}{W}{W}", cmc=4, type_line="Sorcery",
             oracle_text="Destroy all creatures. They can't be regenerated.")
ONE_SIDED = Card(name="Plague Wind", mana_cost="{7}{B}{B}", cmc=9, type_line="Sorcery",
                 oracle_text="Destroy all creatures you don't control. They can't be regenerated.")
CYCLER = Card(name="Big Cycler", mana_cost="{6}{G}", cmc=7, type_line="Creature — Beast", oracle_text="Cycling {2}")
LAND_CYCLER = Card(name="Cycling Land", type_line="Land", oracle_text="Cycling {2}")


def board(lands_in_play=0, hand=(), mine=0, theirs=0):
    """A bot (seat 0) looking at a snapshot: its lands and creatures, and an opponent's creatures."""
    bot = BotPlayer("Bot", Deck([COMMANDER], [LAND, CHEAP, PRICEY, WRATH, ONE_SIDED, CYCLER, LAND_CYCLER], []))
    bot.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
    permanent = lambda kind: {"type": kind}
    bot.notify({"event": "state", "hand": list(hand), "seats": [
        {"seat": 0, "lost": False, "battlefield": [permanent("Basic Land")] * lands_in_play + [permanent("Creature")] * mine},
        {"seat": 1, "lost": False, "battlefield": [permanent("Creature")] * theirs}]})
    return bot


class JudgmentTests(unittest.TestCase):
    def test_scry_keeps_lands_until_it_has_enough(self):
        self.assertEqual(board(2).choose(SCRY_PROMPT + LAND.name, [KEEP_ON_TOP, PUT_ON_BOTTOM]), 0)
        self.assertEqual(board(5, hand=[LAND.name]).choose(SCRY_PROMPT + LAND.name, [KEEP_ON_TOP, PUT_ON_BOTTOM]), 1)

    def test_scry_and_surveil_keep_spells_it_can_cast_soon(self):
        self.assertEqual(board(3).choose(SCRY_PROMPT + CHEAP.name, [KEEP_ON_TOP, PUT_ON_BOTTOM]), 0)
        self.assertEqual(board(3).choose(SURVEIL_PROMPT + PRICEY.name, [KEEP_ON_TOP, PUT_IN_GRAVEYARD]), 1)

    def test_modes_prefer_removal_and_skip_costly_extras(self):
        modes = ["You gain 2 life.", "Destroy target artifact.", "Draw a card."]
        self.assertEqual(board().choose(MODE_PROMPT + "Charm", modes), 1)
        self.assertEqual(board().choose(MODE_PROMPT + "Charm", ["Each player discards a card. You lose 2 life.",
                                                               DONE_MODES]), 1)

    def test_casts_a_wipe_only_when_behind_on_creatures(self):
        options = [PASS, CAST + WRATH.name]
        self.assertEqual(board(4, mine=1, theirs=3).choose("Priority: main1", options), 1)
        self.assertEqual(board(4, mine=2, theirs=2).choose("Priority: main1", options), 0)
        self.assertEqual(board(9, mine=3, theirs=1).choose("Priority: main1", [PASS, CAST + ONE_SIDED.name]), 1)

    def test_casts_the_adventure_half_of_a_card(self):
        theft = Card(name="Petty Theft", mana_cost="{1}{U}", cmc=2, type_line="Instant \u2014 Adventure")
        borrower = Card(name="Brazen Borrower", mana_cost="{1}{U}{U}", cmc=3, type_line="Creature \u2014 Faerie Rogue", alternate=theft)
        bot = BotPlayer("Bot", Deck([COMMANDER], [LAND, borrower], []))
        self.assertEqual(bot.choose("Priority: main1", [PASS, CAST + theft.name]), 1)
        self.assertEqual(bot.choose("Priority: main1", [PASS, CAST + theft.name, CAST + borrower.name]), 2, "the dearer of the two")
        self.assertEqual(bot.choose("Priority: main1", [PASS, CAST + CHEAP.name, CAST + theft.name]), 2, "the half counts at its own mana value")

    def test_a_cast_it_does_not_know_does_not_crash_the_choice(self):
        bot = BotPlayer("Bot", Deck([COMMANDER], [LAND, PRICEY], []))
        self.assertEqual(bot.choose("Priority: main1", [PASS, CAST + "Mystery Spell", CAST + PRICEY.name]), 2)

    def test_cycles_extra_lands_and_expensive_spells(self):
        self.assertEqual(board(6).choose("Priority: main1", [PASS, CYCLE + LAND_CYCLER.name]), 1)
        self.assertEqual(board(2).choose("Priority: main1", [PASS, CYCLE + LAND_CYCLER.name]), 0)
        self.assertEqual(board(2).choose("Priority: main1", [PASS, CYCLE + CYCLER.name]), 1)
        self.assertEqual(board(5).choose("Priority: main1", [PASS, CYCLE + CYCLER.name]), 0)


class GoldfishTests(unittest.TestCase):
    def test_reproducible(self):
        self.assertEqual(goldfish(deck(37, 62), games=200, seed=1), goldfish(deck(37, 62), games=200, seed=1))

    def test_all_lands_hits_every_drop_and_mulligans_twice(self):
        stats = goldfish(deck(99, 0), games=50, turns=4)
        self.assertEqual(stats.land_drop_rate, {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0})
        self.assertEqual(stats.mulligan_rate, 1.0)
        self.assertEqual(stats.average_opening_lands, 6.0)  # kept at two mulligans, one bottomed

    def test_no_lands_misses_everything(self):
        stats = goldfish(deck(0, 99), games=20, turns=3)
        self.assertEqual(stats.land_drop_rate, {1: 0.0, 2: 0.0, 3: 0.0})

    def test_typical_commander_mana_base(self):
        stats = goldfish(deck(37, 62), games=2000, turns=4)
        self.assertLess(stats.mulligan_rate, 0.25)
        self.assertGreater(stats.land_drop_rate[3], stats.land_drop_rate[4])
        self.assertGreater(stats.land_drop_rate[1], 0.95)


if __name__ == "__main__":
    unittest.main()
