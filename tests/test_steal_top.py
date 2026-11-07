"""Exile the top card of an opponent's library and cast it with mana of any color (#658): Stolen Strategy (each opponent, spells only,
until end of turn), Brainstealer Dragon (each opponent, played for as long as the cards remain exiled; an opponent's permanent entering
under your control costs its owner life equal to its mana value) and Cunning Rhetoric (the player who attacked you)."""

import unittest

from infernal_machine.game import CAST_EXILE, PLAY_EXILE, Permanent
from tests.helpers import BEAR, FOREST, MOUNTAIN, fire, pick, real, run_stack, table3

STRATEGY = real("Stolen Strategy", "{4}{R}", "Enchantment",
                "At the beginning of your upkeep, exile the top card of each opponent's library. Until end of turn, you may cast spells from "
                "among those exiled cards, and you may spend mana as though it were mana of any color to cast those spells.", colors=("R",))
DRAGON = real("Brainstealer Dragon", "{5}{B}{B}", "Creature — Dragon Horror",
              "Flying\nAt the beginning of your end step, exile the top card of each opponent's library. You may play those cards for as long "
              "as they remain exiled. If you cast a spell this way, you may spend mana as though it were mana of any color to cast it.\n"
              "Whenever a nonland permanent an opponent owns enters the battlefield under your control, they lose life equal to its mana value.",
              "6", "6", colors=("B",))
RHETORIC = real("Cunning Rhetoric", "{2}{B}", "Enchantment",
                "Whenever an opponent attacks you and/or one or more planeswalkers you control, exile the top card of that player's library. "
                "You may play that card for as long as it remains exiled, and you may spend mana as though it were mana of any color to cast "
                "it.", colors=("B",))
TWIN_BEARS = real("Green Twins", "{G}{G}", "Creature — Bear", "", "2", "2", colors=("G",))  # green mana only: red lands pay for it "as any color"
CHARM = real("Green Charm", "{G}{G}", "Sorcery", "", colors=("G",))


def red_lands(n):
    return [Permanent(MOUNTAIN) for _ in range(n)]


def names(cards):
    return sorted(c.name for c in cards)


class StolenStrategyTests(unittest.TestCase):
    def upkeep(self):
        game, _ = table3(pick("Green"))
        a, b, c = game.seats
        b.library, c.library = [TWIN_BEARS, FOREST], [FOREST, CHARM]
        a.battlefield = [Permanent(STRATEGY)] + red_lands(2)
        fire(game, a, a.battlefield[0], "upkeep")
        return game, a, b, c

    def test_each_opponents_top_card_is_exiled_and_a_spell_cast_with_any_mana(self):
        game, a, b, c = self.upkeep()
        self.assertEqual(names(a.exile), ["Forest", "Green Twins"])
        self.assertIn(CAST_EXILE + "Green Twins", game.legal_actions(a))
        game._perform(a, CAST_EXILE + "Green Twins")
        run_stack(game)
        self.assertIn("Green Twins", [p.card.name for p in a.battlefield])

    def test_a_land_among_them_cannot_be_played(self):
        game, a, b, c = self.upkeep()
        self.assertNotIn(PLAY_EXILE + "Forest", game.legal_actions(a))

    def test_the_permission_ends_with_the_turn(self):
        game, a, b, c = self.upkeep()
        game.turn += 3
        self.assertNotIn(CAST_EXILE + "Green Twins", game.legal_actions(a))


class BrainstealerDragonTests(unittest.TestCase):
    def end_step(self):
        game, _ = table3(pick("Green"))
        a, b, c = game.seats
        b.library, c.library = [TWIN_BEARS], [FOREST]
        a.battlefield = [Permanent(DRAGON, sick=False)] + red_lands(2)
        fire(game, a, a.battlefield[0], "end_step")
        return game, a, b, c

    def test_the_cards_may_still_be_played_on_a_later_turn(self):
        game, a, b, c = self.end_step()
        game.turn += 3
        actions = game.legal_actions(a)
        self.assertIn(CAST_EXILE + "Green Twins", actions)
        self.assertIn(PLAY_EXILE + "Forest", actions)

    def test_a_stolen_permanent_entering_costs_its_owner_its_mana_value(self):
        game, a, b, c = self.end_step()
        game._perform(a, CAST_EXILE + "Green Twins")
        run_stack(game)
        self.assertEqual((b.life, c.life, a.life), (38, 40, 40))

    def test_its_controllers_own_permanent_costs_nothing(self):
        game, a, b, c = self.end_step()
        a.hand = [TWIN_BEARS]
        a.battlefield += [Permanent(FOREST), Permanent(FOREST)]
        game._perform(a, "Cast: Green Twins")
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (40, 40, 40))


    def test_an_opponents_land_played_this_way_stays_theirs_and_costs_nothing(self):
        game, a, b, c = self.end_step()
        game.step = "main1"
        seen, forward = [], game.broadcast
        game.broadcast = lambda event, skip=None: (seen.append(event), forward(event, skip))[1]
        game._perform(a, PLAY_EXILE + "Forest")
        run_stack(game)
        forest = next(p for p in a.battlefield if p.card.name == "Forest")
        self.assertIs(game.owner_of(forest), c)
        self.assertEqual([e for e in seen if e.get("event") == "trigger"], [])  # (a land: "a nonland permanent" only)

    def test_a_permanent_its_controller_owns_costs_nothing_even_marked_with_an_owner(self):
        game, a, b, c = self.end_step()
        game._enter(a, Permanent(TWIN_BEARS, owner=a))
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (40, 40, 40))


class CunningRhetoricTests(unittest.TestCase):
    def attack(self, target):
        game, _ = table3(None, pick(f"Attack Player: {target}"))
        a, b, c = game.seats
        a.battlefield = [Permanent(RHETORIC)] + red_lands(2)
        b.battlefield, b.library = [Permanent(BEAR, sick=False)], [TWIN_BEARS, FOREST]
        game.active, game.step = 1, "declare_attackers"
        game.combat.declare_attackers(b)
        run_stack(game)
        return game, a, b, c

    def test_the_attackers_top_card_may_be_played_with_any_mana_from_then_on(self):
        game, a, b, c = self.attack("A")
        self.assertEqual(names(a.exile), ["Green Twins"])
        game.turn += 3
        game.active, game.step = 0, "main1"
        game._perform(a, CAST_EXILE + "Green Twins")
        run_stack(game)
        self.assertIn("Green Twins", [p.card.name for p in a.battlefield])

    def test_an_attack_on_another_player_sets_nothing_off(self):
        game, a, b, c = self.attack("C")
        self.assertEqual(a.exile, [])


if __name__ == "__main__":
    unittest.main()
