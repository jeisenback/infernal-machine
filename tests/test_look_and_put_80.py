"""Looking at the top cards and putting an Aura or Equipment onto the battlefield (issue #80): Armored Skyhunter first.

Lines are the cards' own Oracle text from Scryfall. Each has cases where nothing is put onto the battlefield.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, card, fire, FOREST, pick, RELIC, run_stack, table3

SKYHUNTER = card("Flying\nWhenever this creature attacks, look at the top six cards of your library. You may put an Aura or "
                 "Equipment card from among them onto the battlefield. If an Equipment is put onto the battlefield this way, "
                 "you may attach it to a creature you control. Put the rest of those cards on the bottom of your library in a "
                 "random order.", "Skyhunter", "Creature — Cat Knight")
BOON = Card(name="Boon", mana_cost="{1}{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature\nEnchanted creature gets +1/+1.")
SWORD = Card(name="Sword", mana_cost="{2}", type_line="Artifact — Equipment", oracle_text="Equipped creature gets +2/+0.\nEquip {2}")
BLIGHT = Card(name="Blight", mana_cost="{1}{B}", type_line="Enchantment — Aura", oracle_text="Enchant land\nEnchanted land has \"{T}: Add {B}.\"")


class SkyhunterTests(unittest.TestCase):
    def attack(self, top, *choices, lands=False):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.hunter = Permanent(SKYHUNTER)
        self.bear = Permanent(BEAR)
        a.battlefield = [self.hunter, self.bear]
        a.library = list(top) + [FOREST] * 10
        fire(game, a, self.hunter, "attacks")
        return a

    def names(self, seat):
        return sorted(p.card.name for p in seat.battlefield)

    def test_parse(self):
        self.assertEqual(unsupported_lines(SKYHUNTER), [])

    def test_an_aura_enters_attached_to_a_creature(self):
        a = self.attack([FOREST, BOON, FOREST, FOREST, FOREST, FOREST], "Boon", "Bear")
        boon = next(p for p in a.battlefield if p.card.name == "Boon")
        self.assertIs(boon.attached_to, self.bear)
        self.assertEqual(len(a.library), 15)  # 16 cards, one taken; the rest went underneath

    def test_an_equipment_enters_and_may_be_attached(self):
        a = self.attack([SWORD, FOREST, FOREST, FOREST, FOREST, FOREST], "Sword", "Bear")
        sword = next(p for p in a.battlefield if p.card.name == "Sword")
        self.assertIs(sword.attached_to, self.bear)

    def test_an_equipment_may_stay_unattached(self):
        a = self.attack([SWORD, FOREST, FOREST, FOREST, FOREST, FOREST], "Sword", "Don't")
        sword = next(p for p in a.battlefield if p.card.name == "Sword")
        self.assertIsNone(sword.attached_to)

    def test_taking_none_puts_everything_underneath(self):
        a = self.attack([BOON, FOREST, FOREST, FOREST, FOREST, FOREST], "Take none")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])
        self.assertEqual(len(a.library), 16)

    def test_no_aura_or_equipment_among_them_does_nothing(self):
        a = self.attack([FOREST, RELIC, FOREST, FOREST, FOREST, FOREST], "Relic")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])
        self.assertEqual(len(a.library), 16)

    def test_only_the_top_six_are_looked_at(self):
        a = self.attack([FOREST] * 6 + [BOON], "Boon")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])

    def test_an_aura_with_nothing_to_enchant_is_not_offered(self):
        a = self.attack([BLIGHT, FOREST, FOREST, FOREST, FOREST, FOREST], "Blight")
        self.assertEqual(self.names(a), ["Bear", "Skyhunter"])
        self.assertEqual(len(a.library), 16)


SONGBIRDS = Card(name="Songbirds' Blessing", mana_cost="{1}{G}", type_line="Enchantment — Aura",
                 oracle_text="Enchant creature\nWhenever enchanted creature attacks, reveal cards from the top of your library "
                             "until you reveal an Aura card. You may put that card onto the battlefield. If you don't, put it "
                             "into your hand. Put the rest on the bottom of your library in a random order.")


class SongbirdsBlessingTests(unittest.TestCase):
    def attack(self, library, *choices):
        game, _ = table3(pick(*choices))
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        songbirds = Permanent(SONGBIRDS, attached_to=bear)
        a.battlefield = [bear, songbirds]
        a.library = list(library)
        game.trigger("host_attacks", songbirds, a, bear)
        run_stack(game)
        return a

    def names(self, seat):
        return sorted(p.card.name for p in seat.battlefield)

    def test_parse(self):
        self.assertEqual(unsupported_lines(SONGBIRDS), [])

    def test_the_aura_may_be_put_onto_the_battlefield(self):
        a = self.attack([FOREST, FOREST, BOON, RELIC], "Yes", "Bear")
        self.assertEqual(self.names(a), ["Bear", "Boon", "Songbirds' Blessing"])
        self.assertEqual(sorted(c.name for c in a.library), ["Forest", "Forest", "Relic"])

    def test_declining_puts_it_into_the_hand(self):
        a = self.attack([FOREST, BOON, RELIC], "No")
        self.assertEqual([c.name for c in a.hand], ["Boon"])
        self.assertEqual(self.names(a), ["Bear", "Songbirds' Blessing"])

    def test_the_cards_below_the_aura_stay_in_place(self):
        a = self.attack([FOREST, BOON, RELIC, RELIC], "No")
        self.assertEqual([c.name for c in a.library][:2], ["Relic", "Relic"])  # untouched, on top; the revealed Forest went under

    def test_an_aura_with_nothing_to_enchant_goes_to_the_hand(self):
        a = self.attack([BLIGHT, FOREST], "Yes")
        self.assertEqual([c.name for c in a.hand], ["Blight"])

    def test_no_aura_in_the_library_puts_every_card_back_underneath(self):
        a = self.attack([FOREST, RELIC, FOREST])
        self.assertEqual((a.hand, len(a.library)), ([], 3))


HERALD = card("Flying\nWhen this creature enters, exile the top eight cards of your library. You may cast an Aura spell from "
              "among them without paying its mana cost. Then put the rest on the bottom of your library in a random order.\n"
              "Whenever this creature attacks, it gets +X/+X until end of turn, where X is the number of Auras you control.",
              "Herald", "Creature — Griffin")


class HeraldOfAmityTests(unittest.TestCase):
    def enter(self, top, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        herald, bear = Permanent(HERALD), Permanent(BEAR)
        a.battlefield = [herald, bear]
        a.library = list(top) + [FOREST] * 10
        fire(game, a, herald, "enters")
        return a, bear

    def names(self, seat):
        return sorted(p.card.name for p in seat.battlefield)

    def test_parse(self):
        self.assertEqual(unsupported_lines(HERALD), [])

    def test_an_aura_is_cast_for_free_and_the_rest_go_underneath(self):
        a, bear = self.enter([FOREST, BOON] + [RELIC] * 6, "Boon", "Bear")
        boon = next(p for p in a.battlefield if p.card.name == "Boon")
        self.assertIs(boon.attached_to, bear)
        self.assertEqual((a.exile, len(a.library)), ([], 17))  # 18 cards, 8 exiled, 7 back underneath, 10 below

    def test_declining_puts_all_eight_underneath(self):
        a, bear = self.enter([FOREST, BOON] + [RELIC] * 6, "Take none")
        self.assertEqual((self.names(a), a.exile, len(a.library)), (["Bear", "Herald"], [], 18))

    def test_no_aura_among_them_does_nothing(self):
        a, bear = self.enter([RELIC] * 8)
        self.assertEqual((self.names(a), a.exile, len(a.library)), (["Bear", "Herald"], [], 18))

    def test_an_aura_with_no_legal_target_is_not_offered(self):
        a, bear = self.enter([BLIGHT] + [RELIC] * 7, "Blight")
        self.assertEqual((self.names(a), a.exile, len(a.library)), (["Bear", "Herald"], [], 18))

    def test_only_the_top_eight_are_exiled(self):
        a, bear = self.enter([FOREST] * 8 + [BOON], "Boon")
        self.assertEqual(self.names(a), ["Bear", "Herald"])


FILIBUSTER = Card(name="Forum Filibuster", mana_cost="{3}{W}", type_line="Enchantment",
                  oracle_text="At the beginning of your upkeep, create a 2/1 white and black Inkling creature token with flying. "
                              "When you do, return up to one target Aura or Equipment card from your graveyard to the "
                              "battlefield attached to that token.")


class ForumFilibusterTests(unittest.TestCase):
    def upkeep(self, graveyard, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        filibuster = Permanent(FILIBUSTER)
        a.battlefield = [filibuster]
        a.graveyard = list(graveyard)
        fire(game, a, filibuster, "upkeep")
        return a

    def inkling(self, seat):
        return next((p for p in seat.battlefield if p.card.name == "Inkling"), None)

    def test_parse(self):
        self.assertEqual(unsupported_lines(FILIBUSTER), [])

    def test_the_token_comes_with_an_aura_from_the_graveyard(self):
        a = self.upkeep([BOON, RELIC], "Boon")
        boon = next(p for p in a.battlefield if p.card.name == "Boon")
        self.assertIs(boon.attached_to, self.inkling(a))
        self.assertEqual([c.name for c in a.graveyard], ["Relic"])

    def test_or_an_equipment(self):
        a = self.upkeep([SWORD], "Sword")
        sword = next(p for p in a.battlefield if p.card.name == "Sword")
        self.assertIs(sword.attached_to, self.inkling(a))

    def test_an_empty_graveyard_still_makes_the_token(self):
        a = self.upkeep([])
        self.assertIsNotNone(self.inkling(a))

    def test_it_may_be_declined(self):
        a = self.upkeep([BOON], "Take none")
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.graveyard]),
                         (["Forum Filibuster", "Inkling"], ["Boon"]))

    def test_an_aura_that_cannot_enchant_the_token_is_not_offered(self):
        a = self.upkeep([BLIGHT], "Blight")
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.graveyard]),
                         (["Forum Filibuster", "Inkling"], ["Blight"]))


AO = Card(name="Ao, the Dawn Sky", mana_cost="{3}{W}{W}", type_line="Legendary Creature — Dragon Spirit", power="5", toughness="4",
          oracle_text="Flying, vigilance\nWhen Ao dies, choose one —\n• Look at the top seven cards of your library. Put any "
                      "number of nonland permanent cards with total mana value 4 or less from among them onto the battlefield. "
                      "Put the rest on the bottom of your library in a random order.\n• Put two +1/+1 counters on each permanent "
                      "you control that's a creature or Vehicle.")
PAIR = Card(name="Pair", mana_cost="{1}{G}", cmc=2.0, type_line="Creature — Bear", power="2", toughness="2")
TRIPLE = Card(name="Triple", mana_cost="{2}{G}", cmc=3.0, type_line="Creature — Bear", power="3", toughness="3")
IDOL = Card(name="Idol", mana_cost="{1}", cmc=1.0, type_line="Artifact")
BOON2 = Card(name="Boon2", mana_cost="{1}{W}", cmc=2.0, type_line="Enchantment — Aura", oracle_text="Enchant creature")
SPELL = Card(name="Bolt", mana_cost="{R}", cmc=1.0, type_line="Instant")
CART = Card(name="Cart", type_line="Artifact — Vehicle", power="3", toughness="3")


class AoTheDawnSkyTests(unittest.TestCase):
    def dies(self, mode, top=(), *choices):
        game, _ = table3(pick(mode, *choices))
        a = game.seats[0]
        ao = Permanent(AO)
        self.pair = Permanent(PAIR)
        a.battlefield = [ao, self.pair]
        a.library = list(top) + [FOREST] * 10
        fire(game, a, ao, "dies")
        return a

    def names(self, seat):
        return sorted(p.card.name for p in seat.battlefield)

    def test_parse(self):
        self.assertEqual(unsupported_lines(AO), [])

    def test_cards_totalling_four_or_less_enter(self):
        a = self.dies("Look at", (PAIR, TRIPLE, IDOL, SPELL, FOREST), "Pair", "Idol", "Take none")
        self.assertEqual(self.names(a), ["Ao, the Dawn Sky", "Idol", "Pair", "Pair"])
        self.assertEqual(len(a.library), 13)  # 15 cards, 2 taken

    def test_a_card_that_would_go_over_the_total_is_not_offered(self):
        a = self.dies("Look at", (PAIR, TRIPLE), "Pair", "Triple")  # Triple (3) no longer fits in 2
        self.assertEqual(self.names(a), ["Ao, the Dawn Sky", "Pair", "Pair"])

    def test_lands_and_spells_are_never_put_onto_the_battlefield(self):
        a = self.dies("Look at", (FOREST, SPELL), "Forest", "Bolt")
        self.assertEqual(self.names(a), ["Ao, the Dawn Sky", "Pair"])

    def test_an_aura_goes_onto_a_creature(self):
        a = self.dies("Look at", (BOON2,), "Boon2", "Pair")
        boon = next(p for p in a.battlefield if p.card.name == "Boon2")
        self.assertIs(boon.attached_to, self.pair)

    def test_an_aura_with_nothing_to_enchant_is_not_offered(self):
        a = self.dies("Look at", (BLIGHT,), "Blight")
        self.assertEqual((self.names(a), len(a.library)), (["Ao, the Dawn Sky", "Pair"], 11))

    def test_only_the_top_seven_are_looked_at(self):
        a = self.dies("Look at", [FOREST] * 7 + [IDOL], "Idol")
        self.assertEqual(self.names(a), ["Ao, the Dawn Sky", "Pair"])

    def test_taking_none_leaves_everything_underneath(self):
        a = self.dies("Look at", (IDOL,), "Take none")
        self.assertEqual((self.names(a), len(a.library)), (["Ao, the Dawn Sky", "Pair"], 11))

    def test_the_counter_mode_covers_creatures_and_vehicles_only(self):
        game, _ = table3(pick("Put two"))
        a, b, _ = game.seats
        ao, cart, idol, theirs = Permanent(AO), Permanent(CART), Permanent(IDOL), Permanent(PAIR)
        a.battlefield, b.battlefield = [ao, cart, idol], [theirs]
        fire(game, a, ao, "dies")
        self.assertEqual([p.counters.get("+1/+1") for p in (ao, cart, idol, theirs)], [2, 2, None, None])


PLARGG = Card(name="Plargg and Nassari", mana_cost="{3}{U}{R}", type_line="Legendary Creature — Orc Efreet", power="4", toughness="4",
              oracle_text="At the beginning of your upkeep, each player exiles cards from the top of their library until they "
                          "exile a nonland card. An opponent chooses a nonland card exiled this way. You may cast up to two "
                          "spells from among the other cards exiled this way without paying their mana costs.")
ALPHA = Card(name="Alpha", mana_cost="{2}{G}", cmc=3.0, type_line="Creature — Bear", power="2", toughness="2")
BETA = Card(name="Beta", mana_cost="{3}{R}", cmc=4.0, type_line="Creature — Imp", power="2", toughness="2")
GAMMA = Card(name="Gamma", mana_cost="{4}{U}", cmc=5.0, type_line="Creature — Drake", power="2", toughness="2")


class PlarggAndNassariTests(unittest.TestCase):
    def upkeep(self, libraries, mine, aside, casts=None):
        self.offered = []

        def casting(prompt, options):
            self.offered.append(list(options))
            return pick(*mine)(prompt, options)
        game, _ = table3(casting, pick(aside))
        a, b, c = game.seats
        plargg = Permanent(PLARGG)
        a.battlefield = [plargg]
        for seat, library in zip(game.seats, libraries):
            seat.library = list(library) + [FOREST] * 5
        if casts is None:
            fire(game, a, plargg, "upkeep")
        else:
            game.exile_until_nonland_and_cast(a, casts)
            run_stack(game)
        return game

    def names(self, seat, zone="battlefield"):
        return sorted(getattr(p, "card", p).name for p in getattr(seat, zone))

    def test_parse(self):
        self.assertEqual(unsupported_lines(PLARGG), [])

    def test_the_others_are_cast_free_and_the_chosen_one_stays_exiled(self):
        game = self.upkeep([[FOREST, FOREST, ALPHA], [BETA], [FOREST, GAMMA]], ["Alpha", "Beta"], aside="Gamma")
        a, b, c = game.seats
        self.assertEqual(self.names(a), ["Alpha", "Beta", "Plargg and Nassari"])  # Beta was b's card, cast by a
        self.assertEqual(self.names(b), [])
        self.assertEqual(self.names(c, "exile"), ["Forest", "Gamma"])

    def test_the_chosen_card_is_not_offered(self):
        self.upkeep([[ALPHA], [BETA], [GAMMA]], ["Alpha", "Beta"], aside="Gamma")
        self.assertTrue(all("Gamma" not in options for options in self.offered))

    def test_lands_are_exiled_but_never_cast(self):
        game = self.upkeep([[FOREST, ALPHA], [BETA], [GAMMA]], ["Alpha", "Beta"], aside="Beta")
        a = game.seats[0]
        self.assertEqual(self.names(a, "exile"), ["Forest"])

    def test_at_most_the_number_allowed_are_cast(self):
        game = self.upkeep([[ALPHA], [BETA], [GAMMA]], ["Alpha", "Beta"], aside="Gamma", casts=1)
        self.assertEqual(sorted(p.card.name for s in game.seats for p in s.battlefield), ["Alpha", "Plargg and Nassari"])

    def test_declining_casts_nothing(self):
        game = self.upkeep([[ALPHA], [BETA], [GAMMA]], ["Take none"], aside="Gamma")
        self.assertEqual(self.names(game.seats[0]), ["Plargg and Nassari"])

    def test_a_player_with_an_empty_library_is_skipped(self):
        game = self.upkeep([[ALPHA], [], [GAMMA]], ["Alpha"], aside="Gamma")
        self.assertEqual(self.names(game.seats[0]), ["Alpha", "Plargg and Nassari"])
