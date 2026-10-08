import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Replacements, replacement_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import DIVINATION, lands, pick, table

RIP = Card(name="Rest in Peace", mana_cost="{1}{W}", type_line="Enchantment",
           oracle_text="When Rest in Peace enters the battlefield, exile all cards from all graveyards.\n"
                       "If a card or token would be put into a graveyard from anywhere, exile it instead.")
LEYLINE = REAL["Leyline of the Void"]
SEASON = Card(name="Doubling Season", mana_cost="{4}{G}", type_line="Enchantment",
              oracle_text="If an effect would create one or more tokens under your control, it creates twice that many "
                          "of those tokens instead.\nIf an effect would put one or more counters on a permanent you "
                          "control, it puts twice that many of those counters instead.")
LIVES = Card(name="Parallel Lives", mana_cost="{3}{G}", type_line="Enchantment",
             oracle_text="If an effect would create one or more tokens under your control, it creates twice that many "
                         "of those tokens instead.")
SCALES = Card(name="Hardened Scales", mana_cost="{G}", type_line="Enchantment",
              oracle_text="If one or more +1/+1 counters would be put on a creature you control, that many plus one "
                          "+1/+1 counters are put on it instead.")
PANH = REAL["Panharmonicon"]
YAROK = Card(name="Yarok", mana_cost="{2}{B}{G}{U}", type_line="Legendary Creature — Elemental", power="3", toughness="5",
             oracle_text="If a permanent entering the battlefield causes a triggered ability of a permanent you control "
                         "to trigger, that ability triggers an additional time.")
SOLDIER = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1")
HEALER = creature("Healer", 2, 2, "When CARDNAME enters, you gain 1 life.")
SHRINE = Card(name="Shrine", mana_cost="{1}", type_line="Enchantment", oracle_text="When CARDNAME enters, you gain 1 life.")
HYDRA = Card(name="Hydra", mana_cost="{2}", type_line="Creature — Hydra", power="0", toughness="0",
             oracle_text="CARDNAME enters with two +1/+1 counters on it.")
MARTYR = creature("Martyr", 1, 1, "When CARDNAME dies, you gain 1 life.")


def names(cards):
    return sorted(c.name for c in cards)


class ParseTests(unittest.TestCase):
    def test_what_each_card_does(self):
        self.assertEqual(replacement_effects(RIP), Replacements(graveyard="any"))
        self.assertEqual(replacement_effects(LEYLINE), Replacements(graveyard="opponent"))
        self.assertEqual(replacement_effects(SEASON), Replacements(tokens=2, counters=2))
        self.assertEqual(replacement_effects(SCALES), Replacements(plus_one=1))
        self.assertEqual(replacement_effects(PANH), Replacements(extra_trigger="artifact or creature"))
        self.assertEqual(replacement_effects(YAROK), Replacements(extra_trigger="permanent"))
        self.assertEqual(replacement_effects(BEAR), Replacements())

    def test_the_report(self):
        for card in (RIP, LEYLINE, SEASON, LIVES, SCALES, PANH, YAROK):
            self.assertEqual(unsupported_lines(card), [], card.name)


class GraveyardTests(unittest.TestCase):
    def test_a_spell_is_exiled_instead(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.battlefield = [Permanent(RIP)] + lands(3)
        a.hand = [DIVINATION]
        game._priority_round(a)
        self.assertEqual((a.graveyard, names(a.exile)), ([], ["Divination"]))

    def test_a_creature_that_dies_is_exiled_but_still_dies(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(RIP)]
        b.battlefield = [Permanent(MARTYR)]
        game.destroy(b.battlefield[0])
        game._priority_round(b)
        self.assertEqual((b.graveyard, names(b.exile), b.life), ([], ["Martyr"], 41))

    def test_entering_exiles_every_graveyard(self):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.hand = [RIP]
        a.battlefield = lands(2)
        a.graveyard, b.graveyard = [BEAR], [OGRE, DIVINATION]
        game._priority_round(a)
        self.assertEqual((a.graveyard, b.graveyard), ([], []))
        self.assertEqual((names(a.exile), names(b.exile)), (names([BEAR]), names([OGRE, DIVINATION])))

    def test_discarding_at_cleanup_is_exiled_too(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(RIP)]
        a.hand = [BEAR] * 8
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual((a.graveyard, len(a.exile), len(a.hand)), ([], 1, 7))

    def test_without_it_cards_go_to_the_graveyard(self):
        game, _, _ = table()
        a = game.seats[0]
        game._move_card(a, BEAR, "graveyard")
        self.assertEqual(a.graveyard, [BEAR])

    def test_leyline_only_exiles_an_opponents_cards(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(LEYLINE)]
        game._move_card(a, BEAR, "graveyard")
        game._move_card(b, OGRE, "graveyard")
        self.assertEqual((a.graveyard, b.graveyard, b.exile), ([BEAR], [], [OGRE]))


class DoublingTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats

    def tokens(self, seat):
        return len([p for p in seat.battlefield if p.card.name == "Soldier"])

    def test_tokens_are_doubled_for_their_controller_only(self):
        self.a.battlefield = [Permanent(LIVES)]
        self.game.create_tokens(self.a, SOLDIER, 2)
        self.game.create_tokens(self.b, SOLDIER, 2)
        self.assertEqual((self.tokens(self.a), self.tokens(self.b)), (4, 2))

    def test_two_doublers_make_four_times_as_many(self):
        self.a.battlefield = [Permanent(LIVES), Permanent(SEASON)]
        self.game.create_tokens(self.a, SOLDIER, 2)
        self.assertEqual(self.tokens(self.a), 8)

    def test_counters_are_doubled_on_your_permanents_only(self):
        mine, theirs = Permanent(BEAR), Permanent(BEAR)
        self.a.battlefield, self.b.battlefield = [Permanent(SEASON), mine], [theirs]
        self.game.put_counters(mine, "+1/+1", 2)
        self.game.put_counters(theirs, "+1/+1", 2)
        self.assertEqual((mine.counters["+1/+1"], theirs.counters["+1/+1"]), (4, 2))

    def test_minus_counters_on_your_creature_are_doubled_too(self):
        mine = Permanent(OGRE)
        self.a.battlefield = [Permanent(SEASON), mine]
        self.game.put_counters(mine, "-1/-1", 1)
        self.assertEqual(mine.counters["-1/-1"], 2)

    def test_counters_a_permanent_enters_with_are_doubled(self):
        self.a.battlefield = [Permanent(SEASON)]
        hydra = Permanent(HYDRA)
        self.game._enter(self.a, hydra)
        self.assertEqual(hydra.counters["+1/+1"], 4)

    def test_hardened_scales_adds_one_to_plus_counters_only(self):
        mine = Permanent(BEAR)
        self.a.battlefield = [Permanent(SCALES), mine]
        self.game.put_counters(mine, "+1/+1", 2)
        self.game.put_counters(mine, "-1/-1", 1)
        self.assertEqual(mine.counters, {"+1/+1": 3, "-1/-1": 1})

    def test_scales_and_doubling_season_together(self):
        mine = Permanent(BEAR)
        self.a.battlefield = [Permanent(SCALES), Permanent(SEASON), mine]
        self.game.put_counters(mine, "+1/+1", 2)
        self.assertEqual(mine.counters["+1/+1"], 6)  # (2 + 1) doubled


class ExtraTriggerTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats

    def enter(self, card, seat=None):
        seat = seat or self.a
        self.game._enter(seat, Permanent(card))
        self.game._priority_round(seat)

    def test_a_creature_entering_triggers_its_ability_twice(self):
        self.a.battlefield = [Permanent(PANH)]
        self.enter(HEALER)
        self.assertEqual(self.a.life, 42)

    def test_an_enchantment_entering_does_not_get_it(self):
        self.a.battlefield = [Permanent(PANH)]
        self.enter(SHRINE)
        self.assertEqual(self.a.life, 41)

    def test_yarok_covers_any_permanent(self):
        self.a.battlefield = [Permanent(YAROK)]
        self.enter(SHRINE)
        self.assertEqual(self.a.life, 42)

    def test_two_of_them_trigger_three_times(self):
        self.a.battlefield = [Permanent(PANH), Permanent(YAROK)]
        self.enter(HEALER)
        self.assertEqual(self.a.life, 43)

    def test_an_opponents_does_not_help_you(self):
        self.b.battlefield = [Permanent(PANH)]
        self.enter(HEALER)
        self.assertEqual(self.a.life, 41)

    def test_a_watching_ability_triggers_again_too(self):
        warden = creature("Warden", 1, 1, "Whenever another creature enters, you gain 1 life.")
        self.a.battlefield = [Permanent(PANH), Permanent(warden)]
        self.enter(BEAR)
        self.assertEqual(self.a.life, 42)

    def test_without_it_a_trigger_happens_once(self):
        self.enter(HEALER)
        self.assertEqual(self.a.life, 41)


if __name__ == "__main__":
    unittest.main()
