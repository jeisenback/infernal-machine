"""The combat-damage triggers of the ninjas: "that player discards", "target creature that player controls", a Ninja or Rogue you
control dealing damage, Yuriko's reveal, and Walker of Secret Ways' "only during your turn"."""

import dataclasses
import unittest

from infernal_machine.effects import RevealTopToHandDrain, activated_abilities, triggered_abilities
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

DISCARDER = real("Okiba-Gang Shinobi", "{3}{B}{B}", "Creature — Rat Ninja", "Ninjutsu {3}{B}\nWhenever this creature deals combat damage to a "
                 "player, that player discards two cards.", "3", "2")
SLITTER = real("Throat Slitter", "{4}{B}", "Creature — Rat Ninja", "Ninjutsu {2}{B}\nWhenever this creature deals combat damage to a player, "
               "destroy target nonblack creature that player controls.", "2", "2")
MISTBLADE = real("Mistblade Shinobi", "{2}{U}", "Creature — Human Ninja", "Ninjutsu {U}\nWhenever this creature deals combat damage to a player, "
                 "you may return target creature that player controls to its owner's hand.", "1", "1")
WALKER = real("Walker of Secret Ways", "{1}{U}", "Creature — Human Ninja", "Ninjutsu {1}{U}\nWhenever this creature deals combat damage to a "
              "player, look at that player's hand.\n{1}{U}: Return target Ninja you control to its owner's hand. Activate only during your turn.",
              "1", "2")
INFILTRATOR = real("Ingenious Infiltrator", "{U}{B}", "Creature — Vedalken Ninja", "Ninjutsu {U}{B}\nWhenever a Ninja you control deals combat "
                   "damage to a player, draw a card.", "2", "3")
THIEF = real("Prosperous Thief", "{2}{U}", "Creature — Human Ninja", "Ninjutsu {1}{U}\nWhenever one or more Ninja or Rogue creatures you "
             "control deal combat damage to a player, create a Treasure token.", "2", "2")
YURIKO = real("Yuriko, the Tiger's Shadow", "{U}{B}", "Legendary Creature — Human Ninja", "Commander ninjutsu {U}{B}\nWhenever a Ninja you control "
              "deals combat damage to a player, reveal the top card of your library and put that card into your hand. Each opponent loses "
              "life equal to that card's mana value.", "1", "3")
BLACK = real("Black Bear", "{1}{B}", "Creature — Bear", "", "2", "2", ("B",))
GREEN = real("Green Bear", "{1}{G}", "Creature — Bear", "", "2", "2", ("G",))
FIVE_DROP = real("Five Drop", "{3}{G}{G}", "Creature — Giant", "", "5", "5")


def hit(*attackers, mine=(), hand=None, policy=None, theirs=(), others=()):
    """Seat A attacks seat B with `attackers` (unblocked) and the damage is dealt; seat C has `others`."""
    game, _ = table3(policy or attack_all)
    a, b, c = game.seats[:3]
    a.hand, a.graveyard = [], []
    a.battlefield = [Permanent(card, sick=False) for card in attackers] + [Permanent(card, sick=True) for card in mine]  # `mine` stay home
    b.battlefield, c.battlefield = [Permanent(card) for card in theirs], [Permanent(card) for card in others]
    if hand is not None:
        b.hand = list(hand)
    game.combat.declare_attackers(a)
    for attack in game.combat.attacks:
        attack.defender = b
    game.combat.declare_blockers()
    game.combat.deal_damage(first_strike_step=False)
    game._check_state()
    return game, a, b, c


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DISCARDER, SLITTER, MISTBLADE, WALKER, INFILTRATOR, THIEF, YURIKO):
            self.assertEqual([l for l in unsupported_lines(card) if "injutsu" not in l], [], card.name)

    def test_the_timing_of_walkers_ability_is_read(self):
        [ability] = activated_abilities(WALKER)
        self.assertEqual(ability.condition.kind, "your_turn")

    def test_yuriko_is_read(self):
        [ability] = [t for t in triggered_abilities(YURIKO)]
        self.assertEqual(ability.effects, (RevealTopToHandDrain(),))


class ThatPlayerTests(unittest.TestCase):
    def test_that_player_discards_two_cards(self):
        game, a, b, c = hit(DISCARDER, hand=[BEAR, OGRE, FIVE_DROP])
        run_stack(game)
        self.assertEqual(len(b.hand), 1)

    def test_only_the_player_dealt_damage_discards(self):
        game, a, b, c = hit(DISCARDER, hand=[BEAR, OGRE, FIVE_DROP])
        c.hand = [BEAR, OGRE]
        run_stack(game)
        self.assertEqual(len(c.hand), 2)

    def test_destroy_a_nonblack_creature_that_player_controls(self):
        game, a, b, c = hit(SLITTER, theirs=[GREEN], others=[GREEN], policy=attack_all)
        run_stack(game)
        self.assertEqual(len(b.battlefield), 0)
        self.assertEqual(len(c.battlefield), 1)

    def test_a_black_creature_is_not_a_target(self):
        game, a, b, c = hit(SLITTER, theirs=[BLACK])
        run_stack(game)
        self.assertEqual(len(b.battlefield), 1)

    def test_the_other_players_creatures_are_not_targets_either(self):
        game, a, b, c = hit(SLITTER, others=[GREEN])
        run_stack(game)
        self.assertEqual(len(c.battlefield), 1)

    def test_return_a_creature_that_player_controls(self):
        game, a, b, c = hit(MISTBLADE, theirs=[OGRE], others=[BEAR], policy=lambda p, o: 1 if o[0] == "Don't attack" else 0)
        run_stack(game)
        self.assertEqual([x.card.name for x in b.battlefield], [])
        self.assertEqual([x.name for x in b.hand], ["Ogre"])
        self.assertEqual(len(c.battlefield), 1)

    def test_target_options_need_the_player(self):
        game, a, b, c = hit(BEAR, theirs=[GREEN], others=[GREEN])
        self.assertEqual(game.target_options("creature that player controls", a), [])
        game.targeting_player = b
        self.assertEqual(len(game.target_options("creature that player controls", a)), 1)


class NinjaWatcherTests(unittest.TestCase):
    def test_a_ninja_dealing_damage_draws_a_card(self):
        game, a, b, c = hit(DISCARDER, mine=[INFILTRATOR])
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_a_creature_that_is_not_a_ninja_does_not(self):
        game, a, b, c = hit(BEAR, mine=[INFILTRATOR])
        run_stack(game)
        self.assertEqual(a.hand, [])

    def test_an_opponents_ninja_does_not(self):
        game, a, b, c = hit(BEAR, mine=[INFILTRATOR])
        game.pending = []
        ninja = Permanent(DISCARDER, sick=False)
        b.battlefield.append(ninja)
        game.damage(c, 3, source=ninja, combat=True)
        run_stack(game)
        self.assertEqual(a.hand, [])

    def test_one_or_more_ninjas_make_one_treasure(self):
        game, a, b, c = hit(DISCARDER, SLITTER, THIEF)
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Treasure"]), 1)

    def test_a_non_ninja_makes_no_treasure(self):
        game, a, b, c = hit(BEAR, mine=[THIEF])
        run_stack(game)
        self.assertEqual([p for p in a.battlefield if p.card.name == "Treasure"], [])


class YurikoTests(unittest.TestCase):
    def test_reveal_the_top_card_and_each_opponent_loses_its_mana_value(self):
        game, a, b, c = hit(BEAR)
        before = (b.life, c.life)
        a.library = [FIVE_DROP, BEAR]
        RevealTopToHandDrain().resolve(game, a, None)
        self.assertEqual([x.name for x in a.hand], ["Five Drop"])
        self.assertEqual([x.name for x in a.library], ["Bear"])
        self.assertEqual((b.life, c.life), (before[0] - 5, before[1] - 5))

    def test_with_an_empty_library_nothing_happens(self):
        game, a, b, c = hit(BEAR)
        a.library = []
        RevealTopToHandDrain().resolve(game, a, None)
        self.assertEqual(a.hand, [])

    def test_it_happens_when_a_ninja_deals_damage(self):
        game, a, b, c = hit(YURIKO)
        a.library = [FIVE_DROP, BEAR]
        before = (b.life, c.life)
        run_stack(game)
        self.assertEqual([x.name for x in a.hand], ["Five Drop"])
        self.assertEqual((b.life, c.life), (before[0] - 5, before[1] - 5))


class WalkerTests(unittest.TestCase):
    def table(self):
        game, _ = table3(script("Pass"))
        a = game.seats[0]
        a.hand, a.battlefield = [], lands(2) + [Permanent(WALKER, sick=False), Permanent(INFILTRATOR, sick=False)]
        return game, a

    def test_it_can_be_used_on_your_turn(self):
        game, a = self.table()
        self.assertTrue([x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Return target Ninja" in x])

    def test_not_on_another_players_turn(self):
        game, a = self.table()
        game.active = 1
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Return target Ninja" in x])


if __name__ == "__main__":
    unittest.main()
