"""The win cards of the Tymna/Thrasios and Sisay decks (#682, from the #520 measurement): Thassa's Oracle (look at the top X, X your
devotion to blue, and win if X is at least the library), Demonic Consultation (name a card, exile the top six, then exile until it is
revealed), Tainted Pact (exile one at a time until one is taken or a name repeats), Tymna the Weaver (pay a life per opponent dealt combat
damage, draw as many) and Sisay, Weatherlight Captain (+1/+1 per color among the other legendary permanents); and the bot's "win" judgment,
which plays the Oracle line."""

import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Deck
from infernal_machine.effects import CONSULT_NAME_PROMPT, PACT_TAKE_PROMPT
from infernal_machine.game import Permanent
from tests.helpers import COMMANDER, FOREST, enter, fire, lands, pick, real, run_stack, table, table3

ORACLE = real("Thassa's Oracle", "{U}{U}", "Creature — Merfolk Wizard",
              "When this creature enters, look at the top X cards of your library, where X is your devotion to blue. Put up to one of them "
              "on top of your library and the rest on the bottom of your library in a random order. If X is greater than or equal to the "
              "number of cards in your library, you win the game. (Each {U} in the mana costs of permanents you control counts toward your "
              "devotion to blue.)", "1", "3", colors=("U",))
CONSULTATION = real("Demonic Consultation", "{B}", "Instant",
                    "Choose a card name. Exile the top six cards of your library, then reveal cards from the top of your library until you "
                    "reveal a card with the chosen name. Put that card into your hand and exile all other cards revealed this way.",
                    colors=("B",))
PACT = real("Tainted Pact", "{1}{B}", "Instant",
            "Exile the top card of your library. You may put that card into your hand unless it has the same name as another card exiled "
            "this way. Repeat this process until you put a card into your hand or you exile two cards with the same name, whichever comes "
            "first.", colors=("B",))
TYMNA = real("Tymna the Weaver", "{1}{W}{B}", "Legendary Creature — Human Cleric",
             "Lifelink\nAt the beginning of each of your postcombat main phases, you may pay X life, where X is the number of opponents that "
             "were dealt combat damage this turn. If you do, draw X cards.\nPartner (You can have two commanders if both have partner.)",
             "2", "2", colors=("W", "B"))
SISAY = real("Sisay, Weatherlight Captain", "{2}{W}", "Legendary Creature — Human Soldier",
             "Sisay gets +1/+1 for each color among other legendary permanents you control.\n{W}{U}{B}{R}{G}: Search your library for a "
             "legendary permanent card with mana value less than Sisay's power, put that card onto the battlefield, then shuffle.",
             "2", "2", colors=("W",))
CARDS = [real(f"Card {i}", "{2}", "Sorcery", "") for i in range(12)]
BLUE = real("Blue Relic", "{U}", "Artifact", "", colors=("U",))
PAIR = real("Twin Legend", "{U}{B}", "Legendary Creature — Spirit", "", "1", "1", colors=("U", "B"))
WHITE = real("White Legend", "{W}", "Legendary Creature — Spirit", "", "1", "1", colors=("W",))
COMMON = real("Red Common", "{R}", "Creature — Goblin", "", "1", "1", colors=("R",))


def oracle_with(library, policy=None, *others):
    game, _, _ = table(policy)
    mine = game.seats[0]
    mine.library = list(library)
    mine.battlefield = list(others)
    enter(game, mine, ORACLE)
    run_stack(game)
    return game, mine


class ThassasOracleTests(unittest.TestCase):
    def test_a_library_no_bigger_than_the_devotion_wins(self):
        game, mine = oracle_with(CARDS[:2])
        self.assertTrue(mine.wins_game)  # devotion 2 (its own {U}{U}), two cards: X >= the library

    def test_an_empty_library_wins(self):
        game, mine = oracle_with([])
        self.assertTrue(mine.wins_game)

    def test_a_bigger_library_does_not_win(self):
        game, mine = oracle_with(CARDS[:3])
        self.assertFalse(mine.wins_game)
        self.assertEqual(len(mine.library), 3)

    def test_other_permanents_add_to_the_devotion(self):
        game, mine = oracle_with(CARDS[:3], None, Permanent(BLUE))
        self.assertTrue(mine.wins_game)  # 3 >= 3

    def test_one_seen_card_may_stay_on_top_and_the_other_goes_to_the_bottom(self):
        game, mine = oracle_with(CARDS[:5], pick("Card 1"))
        self.assertEqual(mine.library[0].name, "Card 1")
        self.assertEqual(mine.library[-1].name, "Card 0")
        self.assertEqual([c.name for c in mine.library[1:4]], ["Card 2", "Card 3", "Card 4"])

    def test_none_may_stay_on_top(self):
        game, mine = oracle_with(CARDS[:5], pick("Keep none"))
        self.assertEqual([c.name for c in mine.library[:3]], ["Card 2", "Card 3", "Card 4"])
        self.assertEqual(sorted(c.name for c in mine.library[3:]), ["Card 0", "Card 1"])


def cast(spell, library, policy):
    game, _, _ = table(policy)
    mine = game.seats[0]
    mine.library = list(library)
    mine.hand = [spell]
    mine.battlefield = lands(2)
    game._perform(mine, f"Cast: {spell.name}")
    run_stack(game)
    return game, mine


class DemonicConsultationTests(unittest.TestCase):
    def test_the_named_card_below_the_top_six_goes_to_the_hand(self):
        game, mine = cast(CONSULTATION, CARDS[:10], pick("Card 8"))
        self.assertEqual([c.name for c in mine.hand], ["Card 8"])
        self.assertEqual(sorted(c.name for c in mine.exile), sorted(f"Card {i}" for i in range(8)))
        self.assertEqual([c.name for c in mine.library], ["Card 9"])

    def test_a_named_card_among_the_top_six_is_exiled_and_the_rest_with_it(self):
        game, mine = cast(CONSULTATION, CARDS[:10], pick("Card 2"))
        self.assertEqual(mine.hand, [])
        self.assertEqual(mine.library, [])
        self.assertEqual(len(mine.exile), 10)

    def test_a_name_outside_the_library_exiles_all_of_it(self):
        game, mine = cast(CONSULTATION, CARDS[:10], pick("Thassa's Oracle"))
        self.assertEqual(mine.library, [])

    def test_the_names_offered_start_with_the_library_and_add_the_cards_in_hand(self):
        asked = []
        game, mine = cast(CONSULTATION, CARDS[:3], lambda prompt, options: asked.append(options) or 0)
        offered = next(o for o in asked if "Card 0" in o)
        self.assertEqual(offered, ["Card 0", "Card 1", "Card 2", "City of Brass"])  # (City of Brass: the lands on the battlefield)


class TaintedPactTests(unittest.TestCase):
    def test_the_first_card_may_be_taken(self):
        game, mine = cast(PACT, CARDS[:4], pick("Yes"))
        self.assertEqual([c.name for c in mine.hand], ["Card 0"])
        self.assertEqual(len(mine.library), 3)

    def test_declined_cards_are_exiled_until_a_name_repeats(self):
        game, mine = cast(PACT, [CARDS[0], FOREST, CARDS[1], FOREST, CARDS[2]], pick("No"))
        self.assertEqual(mine.hand, [])
        self.assertEqual([c.name for c in mine.library], ["Card 2"])
        self.assertEqual(sorted(c.name for c in mine.exile), ["Card 0", "Card 1", "Forest", "Forest"])

    def test_declining_everything_with_no_repeat_exiles_the_library(self):
        game, mine = cast(PACT, CARDS[:5], pick("No"))
        self.assertEqual(mine.library, [])


class TymnaTests(unittest.TestCase):
    def table(self, hit, life=40):
        game, players = table3(pick("Yes"))
        mine = game.seats[0]
        mine.life = life
        mine.library = CARDS[:5]
        tymna = Permanent(TYMNA, sick=False)
        mine.battlefield = [tymna]
        attacker = Permanent(COMMON, sick=False)  # (not Tymna: her lifelink would gain life)
        mine.battlefield.append(attacker)
        for seat in game.seats[1:1 + hit]:
            game.damage(seat, 2, source=attacker, combat=True)
        fire(game, mine, tymna, "second_main")
        return game, mine

    def test_a_life_and_a_card_for_each_opponent_dealt_combat_damage(self):
        game, mine = self.table(2)
        self.assertEqual(mine.life, 38)
        self.assertEqual(len(mine.hand), 2)

    def test_no_opponent_hit_draws_nothing(self):
        game, mine = self.table(0)
        self.assertEqual((mine.life, mine.hand), (40, []))

    def test_combat_damage_on_an_earlier_turn_does_not_count(self):
        game, players = table3(pick("Yes"))
        mine = game.seats[0]
        mine.library = CARDS[:5]
        tymna = Permanent(TYMNA, sick=False)
        attacker = Permanent(COMMON, sick=False)
        mine.battlefield = [tymna, attacker]
        game.damage(game.seats[1], 2, source=attacker, combat=True)
        game.turn += 3
        fire(game, mine, tymna, "second_main")
        self.assertEqual(mine.hand, [])

    def test_noncombat_damage_does_not_count(self):
        game, players = table3(pick("Yes"))
        mine = game.seats[0]
        mine.library = CARDS[:5]
        tymna = Permanent(TYMNA, sick=False)
        mine.battlefield = [tymna]
        game.damage(game.seats[1], 2)
        fire(game, mine, tymna, "second_main")
        self.assertEqual(mine.hand, [])

    def test_life_it_does_not_have_cannot_be_paid(self):
        game, mine = self.table(2, life=1)
        self.assertEqual((mine.life, mine.hand), (1, []))


class SisayTests(unittest.TestCase):
    def power(self, *others):
        game, _, _ = table()
        sisay = Permanent(SISAY)
        game.seats[0].battlefield = [sisay, *others]
        return game.power(sisay)

    def test_each_color_among_the_other_legends_counts_once(self):
        self.assertEqual(self.power(Permanent(PAIR), Permanent(real("Blue Legend", "{U}", "Legendary Artifact", "", colors=("U",)))), 4)

    def test_her_own_color_counts_only_through_another_legend(self):
        self.assertEqual(self.power(), 2)
        self.assertEqual(self.power(Permanent(WHITE)), 3)

    def test_a_permanent_that_is_not_legendary_does_not_count(self):
        self.assertEqual(self.power(Permanent(COMMON)), 2)

    def test_an_opponents_legend_does_not_count(self):
        game, _, _ = table()
        sisay = Permanent(SISAY)
        game.seats[0].battlefield = [sisay]
        game.seats[1].battlefield = [Permanent(PAIR)]
        self.assertEqual(game.power(sisay), 2)


DECK = Deck([COMMANDER], [ORACLE, CONSULTATION, PACT, FOREST, *CARDS[:3]], [])


def bot(features=FEATURES, hand=(), untapped=2, library=40):
    b = BotPlayer("Bot", DECK, features=features)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
    b.notify({"event": "state", "hand": list(hand), "seats": [
        {"seat": 0, "lost": False, "library": library, "mana_pool": [],
         "battlefield": [{"name": "Island", "type": "Basic Land — Island", "tapped": False} for _ in range(untapped)]}]})
    return b


class BotOracleLineTests(unittest.TestCase):
    NAMES = ["Card 0", "Card 1", "Thassa's Oracle"]

    def named(self, b):
        return self.NAMES[b.choose(CONSULT_NAME_PROMPT("Demonic Consultation"), self.NAMES)]

    def test_with_the_oracle_in_hand_and_mana_it_names_the_oracle(self):
        self.assertEqual(self.named(bot(hand=["Thassa's Oracle"])), "Thassa's Oracle")

    def test_without_the_mana_or_the_oracle_it_names_the_first_card(self):
        self.assertEqual(self.named(bot(hand=["Thassa's Oracle"], untapped=1)), "Card 0")
        self.assertEqual(self.named(bot(hand=[])), "Card 0")
        self.assertEqual(self.named(bot(frozenset(), hand=["Thassa's Oracle"])), "Card 0")

    def test_tainted_pact_takes_nothing_while_the_oracle_is_ready(self):
        self.assertEqual(bot(hand=["Thassa's Oracle"]).choose(PACT_TAKE_PROMPT("Card 0"), ["Yes", "No"]), 1)

    def test_tainted_pact_otherwise_takes_a_spell_and_passes_a_land(self):
        self.assertEqual(bot().choose(PACT_TAKE_PROMPT("Card 0"), ["Yes", "No"]), 0)
        self.assertEqual(bot().choose(PACT_TAKE_PROMPT("Forest"), ["Yes", "No"]), 1)
        self.assertEqual(bot(frozenset()).choose(PACT_TAKE_PROMPT("Forest"), ["Yes", "No"]), 0)

    def test_it_casts_the_oracle_first_on_a_small_library(self):
        options = ["Cast: Card 0", "Cast: Thassa's Oracle", "Pass"]
        self.assertEqual(bot(hand=["Card 0", "Thassa's Oracle"], library=2).choose("Your priority", options), 1)

    def test_on_a_big_library_the_oracle_is_just_a_spell(self):
        options = ["Cast: Card 0", "Cast: Thassa's Oracle", "Pass"]
        b = bot(hand=["Card 0", "Thassa's Oracle"], library=3)
        self.assertEqual(options[b.choose("Your priority", options)], "Cast: Card 0")


if __name__ == "__main__":
    unittest.main()
