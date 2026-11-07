"""Kinnan's Basalt Monolith loop (#684): with Kinnan, Bonder Prodigy out, Basalt Monolith's "{3}: Untap this artifact." is paid by tapping
Basalt itself (CR 602.2b: a mana ability may be activated while a cost is paid), which makes three mana and Kinnan's one more: a mana
each time. The bot's "loop" judgment runs it only for somewhere to spend the mana: Walking Ballista's counters and then a point of
damage each to the opponents, Walking Ballista cast from the hand for a big X, or Thrasios digging for the Ballista."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Deck
from infernal_machine.game import PASS, Game, Permanent
from infernal_machine.prompts import PRIORITY_PROMPT
from tests.helpers import COMMANDER, FOREST, real, run_stack, table

BASALT = real("Basalt Monolith", "{3}", "Artifact",
              "This artifact doesn't untap during your untap step.\n{T}: Add {C}{C}{C}.\n{3}: Untap this artifact.")
KINNAN = real("Kinnan, Bonder Prodigy", "{G}{U}", "Legendary Creature — Human Druid",
              "Whenever you tap a nonland permanent for mana, add one mana of any type that permanent produced.\n{5}{G}{U}: Look at the top "
              "five cards of your library. You may put a non-Human creature card from among them onto the battlefield. Put the rest on the "
              "bottom of your library in a random order.", "2", "2", colors=("G", "U"))
BALLISTA = real("Walking Ballista", "{X}{X}", "Artifact Creature — Construct",
                "This creature enters with X +1/+1 counters on it.\n{4}: Put a +1/+1 counter on this creature.\nRemove a +1/+1 counter from "
                "this creature: It deals 1 damage to any target.", "0", "0")
THRASIOS = real("Thrasios, Triton Hero", "{G}{U}", "Legendary Creature — Merfolk Wizard",
                "{4}: Scry 1, then reveal the top card of your library. If it's a land card, put it onto the battlefield tapped. Otherwise, "
                "draw a card.\nPartner (You can have two commanders if both have partner.)", "1", "3", colors=("G", "U"))
FILLER = real("Filler", "{5}", "Sorcery", "")


def untap_basalt(game, seat, times):
    pools = []
    for _ in range(times):
        game._perform(seat, next(a for a in game.legal_actions(seat) if "Untap this artifact" in a))
        run_stack(game)
        pools.append(len(seat.mana_pool))
    return pools


class PaymentTests(unittest.TestCase):
    def test_with_kinnan_each_untap_makes_a_mana(self):
        game, _, _ = table()
        me = game.seats[0]
        basalt = Permanent(BASALT)
        me.battlefield = [basalt, Permanent(KINNAN, sick=False)]
        self.assertEqual(untap_basalt(game, me, 6), [1, 2, 3, 4, 5, 6])  # the pool's mana is kept: Basalt pays for itself
        self.assertFalse(basalt.tapped)

    def test_without_kinnan_it_makes_nothing_and_keeps_the_pool(self):
        game, _, _ = table()
        me = game.seats[0]
        me.battlefield = [Permanent(BASALT)]
        me.mana_pool = [frozenset("C")] * 3
        self.assertEqual(untap_basalt(game, me, 3), [3, 3, 3])


def bot_game(features=FEATURES, battlefield=(), hand=(), library=(FOREST,) * 30, life=10):
    deck = Deck([COMMANDER], [FOREST] * 30, [])
    bot = BotPlayer("Bot", deck, features=features)
    game = Game([(bot, deck), (BotPlayer("Foe", deck), deck)], seed=1)
    game.turn, game.active, game.step = 2, 0, "main1"
    me, foe = game.seats
    me.battlefield, me.hand, me.library, me.command_zone = list(battlefield), list(hand), list(library), []
    foe.life = life
    for seat in game.seats:
        bot.notify({"event": "seat", "seat": seat.index, "name": seat.name, "life": seat.life})
    return game, bot, me, foe


def play_priority(game, bot, me, limit=500):
    """The bot's main phase: what it does with priority until it passes."""
    done = []
    for _ in range(limit):
        game.send_state(me)
        options = game.legal_actions(me) + [PASS]
        action = options[bot.choose(PRIORITY_PROMPT, options)]
        if action == PASS:
            break
        done.append(action)
        game._perform(me, action)
        run_stack(game)
        game._check_state()
    return done


def loops(done):
    return sum("Untap this artifact" in a for a in done)


class BotLoopTests(unittest.TestCase):
    def test_ballista_on_the_battlefield_kills_the_table(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), ballista])
        play_priority(game, bot, me)
        self.assertTrue(foe.lost)

    def test_ballista_from_the_hand_is_cast_big_enough(self):
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False)], hand=[BALLISTA])
        done = play_priority(game, bot, me)
        self.assertTrue(any(a.startswith("Cast: Walking Ballista") for a in done))
        self.assertTrue(foe.lost)

    def test_a_tapped_basalt_is_untapped_with_lands_first(self):  # it doesn't untap in its controller's untap step
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT, tapped=True), Permanent(KINNAN, sick=False), ballista,
                                                   *(Permanent(FOREST) for _ in range(3))])
        play_priority(game, bot, me)
        self.assertTrue(foe.lost)

    def test_not_on_another_players_turn(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), ballista])
        game.active = 1
        self.assertEqual(loops(play_priority(game, bot, me)), 0)

    def test_not_outside_a_main_phase(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), ballista])
        game.step = "upkeep"
        self.assertEqual(loops(play_priority(game, bot, me)), 0)

    def test_thrasios_digs_for_the_ballista(self):
        library = [FILLER, FILLER, BALLISTA] + [FOREST] * 10
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), Permanent(THRASIOS, sick=False)],
                                      library=library)
        play_priority(game, bot, me)
        self.assertTrue(foe.lost)

    def test_thrasios_stops_digging_when_a_dig_takes_nothing(self):  # Narset, Parter of Veils: no second draw a turn
        narset = real("Narset, Parter of Veils", "{1}{U}{U}", "Legendary Planeswalker — Narset",
                      "Each opponent can't draw more than one card each turn.\n−2: Look at the top four cards of your library. You may reveal "
                      "a noncreature, nonland card from among them and put it into your hand. Put the rest on the bottom of your library in "
                      "a random order.")
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), Permanent(THRASIOS, sick=False)],
                                      library=[FILLER] * 20)
        narset_permanent = Permanent(narset)
        narset_permanent.loyalty = 5
        foe.battlefield = [narset_permanent]
        done = play_priority(game, bot, me)
        self.assertLessEqual(sum("Thrasios" in a for a in done), 2)  # one draw, then a dig that takes nothing, then it stops

    def test_a_pump_that_adds_no_counter_stops_the_loop(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), ballista])
        game.put_counters = lambda *args, **kwargs: None  # (a stand-in for an effect that stops counters)
        done = play_priority(game, bot, me)
        self.assertLessEqual(sum("Put a +1/+1 counter" in a for a in done), 2)

    def test_thrasios_stops_before_the_library_runs_out(self):
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), Permanent(THRASIOS, sick=False)],
                                      library=[FILLER] * 8)
        play_priority(game, bot, me)
        self.assertEqual(len(me.library), 5)  # LOOP_LIBRARY
        self.assertFalse(foe.lost)

    def test_nowhere_to_spend_it_means_no_loop(self):
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False)])
        self.assertEqual(loops(play_priority(game, bot, me)), 0)

    def test_without_kinnan_there_is_no_loop(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(battlefield=[Permanent(BASALT), ballista])
        self.assertEqual(loops(play_priority(game, bot, me)), 0)

    def test_without_the_judgment_there_is_no_loop(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 1
        game, bot, me, foe = bot_game(FEATURES - {"loop"}, battlefield=[Permanent(BASALT), Permanent(KINNAN, sick=False), ballista])
        self.assertEqual(loops(play_priority(game, bot, me)), 0)
        self.assertFalse(foe.lost)

    def test_a_ballista_with_enough_counters_finishes_the_table_without_the_loop(self):
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 10
        game, bot, me, foe = bot_game(battlefield=[ballista])
        play_priority(game, bot, me)
        self.assertTrue(foe.lost)

    def test_each_ping_goes_to_the_opponent_on_the_lowest_life(self):
        deck = Deck([COMMANDER], [FOREST] * 30, [])
        bot = BotPlayer("Bot", deck)
        game = Game([(bot, deck), (BotPlayer("A", deck), deck), (BotPlayer("B", deck), deck)], seed=1)
        game.turn, game.active, game.step = 2, 0, "main1"
        me, a, b = game.seats
        for seat in game.seats:
            seat.command_zone = []
        ballista = Permanent(BALLISTA, sick=False)
        ballista.counters["+1/+1"] = 8
        me.battlefield = [ballista]
        a.life, b.life = 5, 3
        for seat in game.seats:
            bot.notify({"event": "seat", "seat": seat.index, "name": seat.name, "life": seat.life})
        play_priority(game, bot, me, limit=4)
        self.assertEqual((a.life, b.life), (4, 0))  # three to B (the lower), then A
        play_priority(game, bot, me)
        self.assertTrue(a.lost and b.lost)

    def test_a_loop_that_makes_nothing_is_stopped(self):
        b = BotPlayer("Bot", Deck([COMMANDER], [FOREST], []))
        b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
        options = ["Activate: Basalt Monolith (seat 0, #1): {3}: Untap this artifact.", "Cast: Walking Ballista", PASS]

        def state(pool):
            b.notify({"event": "state", "turn": 3, "active": 0, "step": "main1", "hand": ["Walking Ballista"], "seats": [
                {"seat": 0, "lost": False, "life": 40, "library": 30, "mana_pool": ["C"] * pool,
                 "battlefield": [{"name": "Basalt Monolith", "type": "Artifact"}, {"name": "Kinnan, Bonder Prodigy", "type": "Creature"}]},
                {"seat": 1, "lost": False, "life": 40, "battlefield": []}]})
        state(0)
        self.assertEqual(b.choose(PRIORITY_PROMPT, options), 0)
        state(0)  # (Kinnan's mana did not come)
        self.assertEqual(b.choose(PRIORITY_PROMPT, options), 1)  # no more untaps this turn: it just casts the Ballista for what it has

    def test_with_the_mana_and_no_sink_on_offer_it_untaps_no_more(self):
        b = BotPlayer("Bot", Deck([COMMANDER], [FOREST], []))
        b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
        b.notify({"event": "state", "turn": 3, "active": 0, "step": "main1", "hand": ["Walking Ballista"], "seats": [
            {"seat": 0, "lost": False, "life": 40, "library": 30, "mana_pool": ["C"] * 90,
             "battlefield": [{"name": "Basalt Monolith", "type": "Artifact"}, {"name": "Kinnan, Bonder Prodigy", "type": "Creature"}]},
            {"seat": 1, "lost": False, "life": 40, "battlefield": []}]})
        options = ["Activate: Basalt Monolith (seat 0, #1): {3}: Untap this artifact.", PASS]  # (no "Cast: Walking Ballista")
        self.assertEqual(options[b.choose(PRIORITY_PROMPT, options)], PASS)


if __name__ == "__main__":
    unittest.main()
