import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.combat import ASSIGN_PROMPT, ATTACK_PROMPT, NO_ATTACK
from infernal_machine.game import Permanent
from tests.helpers import BEAR, creature, FOREST, OGRE, table, WURM

WALKER = Card(name="Walker", mana_cost="{3}", type_line="Legendary Planeswalker — Test", loyalty="4")
DRAGON = creature("Dragon", 4, 4)
GUARD = Card(name="Guard", mana_cost="{1}", type_line="Enchantment",
             oracle_text="Whenever a creature attacks you, you gain 1 life.")
SENTRY = Card(name="Sentry", mana_cost="{1}", type_line="Enchantment",
              oracle_text="Whenever a creature attacks you or a planeswalker you control, you gain 1 life.")


def attack_walker(prompt, options):
    for i, option in enumerate(options):
        if option.startswith("Attack Planeswalker"):
            return i
    return options.index("Pass") if "Pass" in options else 0


def attack_player(prompt, options):
    return 1 if options and options[0] == NO_ATTACK else (options.index("Pass") if "Pass" in options else 0)


def block_everything(prompt, options):
    return 1 if options and options[0] in ("Don't attack", "Don't block") else (
        options.index("Pass") if "Pass" in options else 0)


def combat(attacker_policy, blocker_policy, mine, theirs, walker_loyalty=4):
    game, _, _ = table(attacker_policy, blocker_policy)
    a, b = game.seats
    a.battlefield = [Permanent(c) for c in mine]
    walker = Permanent(WALKER, loyalty=walker_loyalty)
    b.battlefield = [walker] + [Permanent(c) for c in theirs]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    game.combat.deal_damage(first_strike_step=False)
    game._check_state()
    return game, a, b, walker


class AttackingAPlaneswalkerTests(unittest.TestCase):
    def test_the_planeswalker_is_offered_as_a_target(self):
        game, player, _ = table(attack_player)
        a, b = game.seats
        a.battlefield = [Permanent(OGRE)]
        b.battlefield = [Permanent(WALKER, loyalty=4)]
        game.combat.declare_attackers(a)
        offered = next(options for prompt, options in player.prompts if ATTACK_PROMPT.matches(prompt))
        self.assertEqual(len(offered), 3)
        self.assertEqual((offered[0], offered[2].startswith("Attack Planeswalker: Walker")), (NO_ATTACK, True))

    def test_damage_removes_loyalty_not_life(self):
        game, a, b, walker = combat(attack_walker, None, [OGRE], [])
        self.assertEqual((walker.loyalty, b.life), (1, 40))
        self.assertIn(walker, b.battlefield)

    def test_enough_damage_kills_it(self):
        game, a, b, walker = combat(attack_walker, None, [WURM], [])
        self.assertNotIn(walker, b.battlefield)
        self.assertEqual([c.name for c in b.graveyard], ["Walker"])
        self.assertEqual(b.life, 40)

    def test_the_players_creatures_can_block_the_attacker(self):
        game, a, b, walker = combat(attack_walker, block_everything, [OGRE], [BEAR])
        self.assertEqual(walker.loyalty, 4)  # blocked: nothing went through
        self.assertEqual(len(game.combat.attacks[0].blockers), 1)

    def test_trample_goes_through_to_the_planeswalker(self):
        trampler = creature("Trampler", 6, 6, "Trample")
        game, a, b, walker = combat(attack_walker, block_everything, [trampler], [BEAR])
        self.assertNotIn(walker, b.battlefield)  # 2 to the Bear, 4 to the planeswalker

    def test_if_the_planeswalker_left_nothing_is_hit(self):
        game, _, _ = table(attack_walker)
        a, b = game.seats
        a.battlefield = [Permanent(OGRE)]
        walker = Permanent(WALKER, loyalty=4)
        b.battlefield = [walker]
        game.combat.declare_attackers(a)
        b.battlefield = []
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual((b.life, walker.loyalty), (40, 4))  # no damage to the player or to the gone planeswalker

    def test_the_attack_event_names_the_planeswalker(self):
        game, player, _ = table(attack_walker)
        a, b = game.seats
        a.battlefield = [Permanent(OGRE)]
        b.battlefield = [Permanent(WALKER, loyalty=4)]
        game.combat.declare_attackers(a)
        event = next(e for e in player.events if e["event"] == "attack")
        self.assertEqual((event["defender"], event["planeswalker"]), (1, "Walker"))

    def test_attacks_you_triggers_only_for_attacks_on_the_player(self):
        for policy, expected in ((attack_player, 42), (attack_walker, 41)):
            game, _, _ = table(policy)
            a, b = game.seats
            a.battlefield = [Permanent(OGRE)]
            b.battlefield = [Permanent(WALKER, loyalty=4), Permanent(GUARD), Permanent(SENTRY)]
            game.combat.declare_attackers(a)
            game._priority_round(b)
            self.assertEqual(b.life, 40 + (expected - 40), policy.__name__)

    def test_bots_keep_attacking_players(self):
        bot = BotPlayer("A", Deck([FOREST], [OGRE], []))
        options = [NO_ATTACK, "Attack Player: B (seat 1)", "Attack Planeswalker: Walker (seat 1, #1)"]
        self.assertEqual(bot.choose(ATTACK_PROMPT + "Ogre 3/3 (seat 0, #1)", options), 1)


class DamageOrderTests(unittest.TestCase):
    def fight(self, first):
        """A 4/4 attacker blocked by a Bear (2/2) and an Ogre (3/3); `first` is who the attacker's controller names."""
        def attacker(prompt, options):
            if ASSIGN_PROMPT.matches(prompt):
                return next(i for i, option in enumerate(options) if option.startswith(first))
            return attack_player(prompt, options)
        game, _, _ = table(attacker, block_everything)
        a, b = game.seats
        a.battlefield = [Permanent(DRAGON)]
        b.battlefield = [Permanent(BEAR), Permanent(OGRE)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        return sorted(p.card.name for p in b.battlefield), b

    def test_naming_the_bear_first_kills_the_bear(self):
        survivors, b = self.fight("Bear")
        self.assertEqual(survivors, ["Ogre"])  # 2 to the Bear, 2 to the Ogre

    def test_naming_the_ogre_first_kills_the_ogre(self):
        survivors, _ = self.fight("Ogre")
        self.assertEqual(survivors, ["Bear"])  # 3 to the Ogre, 1 to the Bear

    def test_one_blocker_asks_nothing(self):
        game, player, _ = table(attack_player, block_everything)
        a, b = game.seats
        a.battlefield = [Permanent(DRAGON)]
        b.battlefield = [Permanent(BEAR)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual([p for p, _ in player.prompts if p.startswith(ASSIGN_PROMPT)], [])

    def test_the_bot_goes_for_the_weakest_blocker(self):
        bot = BotPlayer("A", Deck([FOREST], [OGRE], []))
        options = ["Ogre 3/3 (seat 1, #1)", "Bear 2/2 (seat 1, #2)"]
        self.assertEqual(bot.choose(ASSIGN_PROMPT + "Dragon 4/4 (seat 0, #1)", options), 1)


if __name__ == "__main__":
    unittest.main()
