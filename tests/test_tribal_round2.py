"""Round two of the deck-driven coverage work (issue #428): a lord that affects every player's creatures of a type, "Whenever a Dragon you
control attacks", a search by creature type, "reveal the top four, put all Goblin cards into your hand", and Corrupted's poison count."""

import dataclasses
import unittest

from infernal_machine.game import CAST, PASS, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, pick, real, run_stack, table

KING = real("Goblin King", "{1}{R}{R}", "Creature — Goblin", "Other Goblins get +1/+1 and have mountainwalk.", "2", "2")
UTVARA = real("Utvara Hellkite", "{6}{R}{R}", "Creature — Dragon", "Flying\nWhenever a Dragon you control attacks, create a 6/6 red Dragon creature token with flying.", "6", "6")
ATARKA = real("Atarka, World Render", "{5}{R}{G}", "Legendary Creature — Dragon",
              "Flying, trample\nWhenever a Dragon you control attacks, it gains double strike until end of turn.", "6", "4")
TRIUMPH = real("Sarkhan's Triumph", "{2}{R}", "Instant", "Search your library for a Dragon creature card, reveal it, put it into your hand, then shuffle.")
RINGLEADER = real("Goblin Ringleader", "{3}{R}", "Creature — Goblin",
                  "Haste (This creature can attack and {T} as soon as it comes under your control.)\nWhen this creature enters, reveal the top four cards of "
                  "your library. Put all Goblin cards revealed this way into your hand and the rest on the bottom of your library in any order.", "2", "2")
SPHERE_LINE = "Corrupted — {T}: Add three mana of any one color. Activate only if an opponent has three or more poison counters."
SPHERE = real("Test Sphere", "{3}", "Artifact", SPHERE_LINE)
GOBLIN = real("Test Goblin", "{R}", "Creature — Goblin", "", "1", "1")
DRAGON = real("Test Dragon", "{4}{R}{R}", "Creature — Dragon", "Flying", "5", "5")
ELF = real("Test Elf", "{G}", "Creature — Elf", "", "1", "1")


def attack_all(prompt, options):
    return 1 if prompt.startswith("Attack with") else (options.index(PASS) if PASS in options else 0)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (KING, UTVARA, ATARKA, TRIUMPH, RINGLEADER, SPHERE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class LordTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats
        self.king = Permanent(KING)
        self.mine, self.theirs, self.bear = Permanent(GOBLIN), Permanent(GOBLIN), Permanent(BEAR)
        self.a.battlefield = [self.king, self.mine, self.bear]
        self.b.battlefield = [self.theirs]

    def test_every_players_goblins_get_the_bonus_and_the_king_and_others_do_not(self):
        g = self.game
        self.assertEqual([g.power(p) for p in (self.mine, self.theirs, self.king, self.bear)], [2, 2, 2, 2])
        self.assertEqual([g.toughness(p) for p in (self.mine, self.theirs, self.king, self.bear)], [2, 2, 2, 2])

    def test_they_have_mountainwalk(self):
        self.assertTrue(self.game.has_keyword(self.mine, "mountainwalk"))
        self.assertTrue(self.game.has_keyword(self.theirs, "mountainwalk"))
        self.assertFalse(self.game.has_keyword(self.king, "mountainwalk"))
        self.assertFalse(self.game.has_keyword(self.bear, "mountainwalk"))

    def test_with_two_kings_each_buffs_the_other(self):
        other = Permanent(KING)
        self.a.battlefield.append(other)
        self.assertEqual((self.game.power(self.king), self.game.power(other), self.game.power(self.mine)), (3, 3, 3))

    def test_without_the_king_nothing_changes(self):
        self.a.battlefield.remove(self.king)
        self.assertEqual((self.game.power(self.mine), self.game.has_keyword(self.mine, "mountainwalk")), (1, False))


class AttackTriggerTests(unittest.TestCase):
    def attack(self, battlefield):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(c, sick=False) for c in battlefield]
        game.combat.declare_attackers(a)
        run_stack(game)
        return game, a

    def test_a_dragon_attacking_makes_a_dragon_token(self):
        _, a = self.attack([UTVARA])
        tokens = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual([(p.card.power, p.card.toughness) for p in tokens], [("6", "6")])
        self.assertIn("Dragon", tokens[0].card.type_line)

    def test_a_creature_that_is_not_a_dragon_does_nothing(self):
        _, a = self.attack([UTVARA, BEAR])
        self.assertEqual(len([p for p in a.battlefield if p.card.type_line.startswith("Token")]), 1, "one trigger, for the Dragon only")

    def test_with_no_dragon_attacking_there_is_no_token(self):
        game, _, _ = table(lambda prompt, options: 1 if prompt.startswith("Attack with") else (options.index(PASS) if PASS in options else 0))
        a = game.seats[0]
        a.battlefield = [Permanent(UTVARA, sick=True), Permanent(BEAR, sick=False)]  # the Dragon has not been here since the turn began
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual([p for p in a.battlefield if p.card.type_line.startswith("Token")], [])

    def test_the_attacking_dragon_gains_double_strike_and_a_bear_does_not(self):
        game, a = self.attack([ATARKA, BEAR])
        atarka, bear = a.battlefield
        self.assertTrue(game.has_keyword(atarka, "double strike"))
        self.assertFalse(game.has_keyword(bear, "double strike"))


class SearchAndRevealTests(unittest.TestCase):
    def test_a_search_by_creature_type_takes_that_type_only(self):
        game, _, _ = table(pick(CAST + "Sarkhan's Triumph", "Test Dragon"))
        a = game.seats[0]
        a.hand = [TRIUMPH]
        a.battlefield = lands(3)
        a.library = [ELF, GOBLIN, DRAGON, FOREST]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Test Dragon"])

    def test_the_search_finds_nothing_without_one(self):
        game, _, _ = table(pick(CAST + "Sarkhan's Triumph"))
        a = game.seats[0]
        a.hand = [TRIUMPH]
        a.battlefield = lands(3)
        a.library = [ELF, GOBLIN, FOREST]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(a.hand, [])

    def test_the_goblins_of_the_top_four_go_to_the_hand_and_the_rest_to_the_bottom(self):
        game, _, _ = table(pick(CAST + "Goblin Ringleader"))
        a = game.seats[0]
        a.hand = [RINGLEADER]
        a.battlefield = lands(4)
        other_goblin = dataclasses.replace(GOBLIN, name="Other Goblin")
        a.library = [ELF, GOBLIN, BEAR, other_goblin, DRAGON, FOREST]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.hand), ["Other Goblin", "Test Goblin"])
        self.assertEqual([c.name for c in a.library], ["Test Dragon", "Forest", "Test Elf", "Bear"], "the unrevealed first, then the rest in order")

    def test_fewer_than_four_cards_is_fine(self):
        game, _, _ = table(pick(CAST + "Goblin Ringleader"))
        a = game.seats[0]
        a.hand = [RINGLEADER]
        a.battlefield = lands(4)
        a.library = [GOBLIN]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], a.library), (["Test Goblin"], []))


class CorruptedTests(unittest.TestCase):
    def mana(self, poison, mine=0):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(SPHERE, sick=False)]
        b.player_counters["poison"] = poison
        a.player_counters["poison"] = mine
        a.hand = [dataclasses.replace(BEAR, name="Three Drop", mana_cost="{3}", cmc=3.0)]
        return CAST + "Three Drop" in game.legal_actions(a)

    def test_it_makes_three_mana_only_once_an_opponent_has_three_poison_counters(self):
        self.assertFalse(self.mana(2))
        self.assertTrue(self.mana(3))
        self.assertTrue(self.mana(7))

    def test_my_own_poison_does_not_count(self):
        self.assertFalse(self.mana(0, mine=5))


if __name__ == "__main__":
    unittest.main()
