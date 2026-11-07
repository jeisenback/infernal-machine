"""Exile the top card of an opponent's library and cast it with mana of any color (#658): Stolen Strategy (each opponent, spells only,
until end of turn), Brainstealer Dragon (each opponent, played for as long as the cards remain exiled; an opponent's permanent entering
under your control costs its owner life equal to its mana value), Cunning Rhetoric (the player who attacked you), Grenzo, Havoc Raiser
(the player a creature dealt combat damage to, as a mode; the other mode goads a creature that player controls) and You Find Some
Prisoners (three of target opponent's cards, one chosen, until the end of your next turn) and Laughing Jasper Flint (as many of target
opponent's cards as the outlaws you control, spells only, until end of turn; the creatures you control but don't own are Mercenaries)."""

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
GRENZO = real("Grenzo, Havoc Raiser", "{R}{R}", "Legendary Creature — Goblin Rogue",
              "Whenever a creature you control deals combat damage to a player, choose one —\n• Goad target creature that player controls.\n"
              "• Exile the top card of that player's library. Until end of turn, you may cast that card and you may spend mana as though it "
              "were mana of any color to cast that spell.", "2", "2", colors=("R",))
PRISONERS = real("You Find Some Prisoners", "{1}{R}", "Instant",
                 "Choose one —\n• Break Their Chains — Destroy target artifact.\n• Interrogate Them — Exile the top three cards of target "
                 "opponent's library. Choose one of them. Until the end of your next turn, you may play that card, and you may spend mana as "
                 "though it were mana of any color to cast it.", colors=("R",))
JASPER = real("Laughing Jasper Flint", "{1}{B}{R}", "Legendary Creature — Lizard Rogue",
              "Creatures you control but don't own are Mercenaries in addition to their other types.\nAt the beginning of your upkeep, exile "
              "the top X cards of target opponent's library, where X is the number of outlaws you control. Until end of turn, you may cast "
              "spells from among those cards, and mana of any type can be spent to cast those spells.", "4", "2", colors=("B", "R"))
PIRATE = real("Deckhand", "{1}{R}", "Creature — Human Pirate", "", "2", "2", colors=("R",))
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


class GrenzoTests(unittest.TestCase):
    def hit(self, answer):
        asked = []

        def policy(prompt, options):
            asked.append(list(options))
            return pick(*answer)(prompt, options)
        game, _ = table3(policy)
        a, b, c = game.seats
        bear = Permanent(BEAR, sick=False)
        a.battlefield = [Permanent(GRENZO, sick=False), bear] + red_lands(2)
        b.library, b.battlefield = [TWIN_BEARS, FOREST], [Permanent(real("Ogre B", "{3}", "Creature — Ogre", "", "3", "3"), sick=False)]
        c.battlefield = [Permanent(real("Ogre C", "{3}", "Creature — Ogre", "", "3", "3"), sick=False)]
        game.damage(b, 2, source=bear, combat=True)
        run_stack(game)
        return game, a, b, c, asked

    def test_the_exile_mode_takes_the_damaged_players_top_card_castable_with_any_mana(self):
        game, a, b, c, asked = self.hit(("Exile the top",))
        self.assertEqual(names(a.exile), ["Green Twins"])
        game._perform(a, CAST_EXILE + "Green Twins")
        run_stack(game)
        self.assertIn("Green Twins", [p.card.name for p in a.battlefield])

    def test_the_goad_mode_targets_only_a_creature_the_damaged_player_controls(self):
        game, a, b, c, asked = self.hit(("Goad", "Ogre C"))  # (it would take C's Ogre if it were offered)
        self.assertIs(b.battlefield[0].goaded_by, a)
        self.assertIsNone(c.battlefield[0].goaded_by)


class YouFindSomePrisonersTests(unittest.TestCase):
    def test_one_of_the_three_cards_may_be_played_through_the_next_turn_with_any_mana(self):
        game, _ = table3(pick("Interrogate", "Exile the top", "Player: B", "Green Twins"))
        a, b, c = game.seats
        a.hand, a.battlefield = [PRISONERS], red_lands(4)
        b.library = [FOREST, TWIN_BEARS, CHARM, FOREST]
        game._perform(a, "Cast: You Find Some Prisoners")
        run_stack(game)
        self.assertEqual(names(a.exile), ["Forest", "Green Charm", "Green Twins"])
        self.assertEqual([(card.name, until) for card, until in a.exile_play], [("Green Twins", game.turn + 3)])
        self.assertEqual(b.library, [FOREST])
        for p in a.battlefield:
            p.tapped = False
        game._perform(a, CAST_EXILE + "Green Twins")
        run_stack(game)
        self.assertIn("Green Twins", [p.card.name for p in a.battlefield])


class LaughingJasperFlintTests(unittest.TestCase):
    def upkeep(self, *others, stolen=False):
        game, _ = table3(pick("Player: B", "Green"))
        a, b, c = game.seats
        others += (Permanent(BEAR, owner=c),) if stolen else ()
        jasper = Permanent(JASPER, sick=False)
        a.battlefield = [jasper, *others] + red_lands(2)
        b.library = [TWIN_BEARS, FOREST, CHARM, FOREST]
        fire(game, a, jasper, "upkeep")
        return game, a, b

    def test_one_card_for_each_outlaw_spells_only_with_any_mana(self):
        game, a, b = self.upkeep(Permanent(PIRATE), Permanent(BEAR))  # Jasper (a Rogue) and the Pirate: two outlaws; the Bear is none
        self.assertEqual(names(a.exile), ["Forest", "Green Twins"])
        actions = game.legal_actions(a)
        self.assertIn(CAST_EXILE + "Green Twins", actions)
        self.assertNotIn(PLAY_EXILE + "Forest", actions)
        game.turn += 3
        self.assertNotIn(CAST_EXILE + "Green Twins", game.legal_actions(a))

    def test_a_creature_you_control_but_dont_own_counts_as_a_mercenary(self):
        game, a, b = self.upkeep(Permanent(BEAR), stolen=True)
        self.assertEqual(len(a.exile), 2)  # Jasper and the stolen Bear; the Bear a owns is none


if __name__ == "__main__":
    unittest.main()
