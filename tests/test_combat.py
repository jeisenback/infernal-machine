import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import Game, Permanent
from tests.helpers import BEAR, OGRE, creature  # noqa: F401  (they live in tests/helpers.py; other tests still import them from here)
from tests.test_effects import FOREST, table
from tests.test_game import ScriptedPlayer


BIRD = creature("Bird", 1, 1, "Flying")
SPIDER = creature("Spider", 1, 3, "Reach")
GOBLIN = creature("Goblin", 2, 1, "Menace")
WURM = creature("Wurm", 6, 6, "Trample")
KNIGHT = creature("Knight", 2, 2, "First strike")
DOUBLE = creature("Double", 2, 2, "Double strike")
SNAKE = creature("Snake", 1, 1, "Deathtouch")
PRIEST = creature("Priest", 2, 2, "Lifelink")
CAT = creature("Cat", 2, 2, "Vigilance")
HASTY = creature("Hasty", 2, 2, "Haste")
WALL = creature("Wall", 0, 4, "Defender")


def attack_all(prompt, options):
    """Attack the first opponent with everything; block the first attacker offered."""
    if len(options) > 1 and options[0] in ("Don't attack", "Don't block"):
        return 1
    return options.index("Pass") if "Pass" in options else 0


def fight(attackers, blockers=(), attacker_policy=attack_all, blocker_policy=attack_all):
    game, _, _ = table(attacker_policy, blocker_policy)
    a, b = game.seats
    a.battlefield = [Permanent(c) for c in attackers]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    if game.combat.has_first_strike():
        game.combat.deal_damage(first_strike_step=True)
        game._check_state()
    game.combat.deal_damage(first_strike_step=False)
    game._check_state()
    return game, a, b


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class AttackTests(unittest.TestCase):
    def test_unblocked_damage_and_tapping(self):
        game, a, b = fight([BEAR, CAT])
        self.assertEqual(b.life, 36)
        self.assertEqual([p.tapped for p in a.battlefield], [True, False])  # vigilance

    def test_who_can_attack(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR, sick=True), Permanent(HASTY, sick=True), Permanent(WALL), Permanent(BEAR, tapped=True)]
        game.combat.declare_attackers(a)
        self.assertEqual([x.attacker.card.name for x in game.combat.attacks], ["Hasty"])

    def test_multiplayer_attack_chooses_defender_and_only_they_block(self):
        players = [ScriptedPlayer("A", lambda p, o: 2 if p.startswith("Attack") else 0),
                   ScriptedPlayer("B", attack_all), ScriptedPlayer("C", attack_all)]
        deck = Deck(commanders=[], main=[FOREST] * 20, sideboard=[])
        game = Game([(p, deck) for p in players], seed=1)
        game.active = 0
        a, b, c = game.seats
        a.battlefield = [Permanent(BEAR)]
        b.battlefield = [Permanent(OGRE)]
        c.battlefield = [Permanent(SPIDER)]
        game.combat.declare_attackers(a)
        self.assertIs(game.combat.attacks[0].defender, c)
        game.combat.declare_blockers()
        self.assertEqual([p.card.name for p in game.combat.attacks[0].blockers], ["Spider"])


class BlockTests(unittest.TestCase):
    def test_trade(self):
        game, a, b = fight([BEAR], [BEAR])
        self.assertEqual((names(a), names(b), b.life), ([], [], 40))

    def test_flying_needs_flying_or_reach(self):
        game, a, b = fight([BIRD], [BEAR])
        self.assertEqual(b.life, 39)
        game, a, b = fight([BIRD], [SPIDER])
        self.assertEqual((b.life, names(a)), (40, []))

    def test_menace_needs_two_blockers(self):
        game, a, b = fight([GOBLIN], [BEAR])
        self.assertEqual((b.life, names(b)), (38, ["Bear"]))
        game, a, b = fight([GOBLIN], [BEAR, BEAR])
        self.assertEqual((names(a), b.life), ([], 40))

    def test_trample(self):
        game, a, b = fight([WURM], [BEAR])
        self.assertEqual((b.life, names(b)), (36, []))

    def test_deathtouch(self):
        game, a, b = fight([OGRE], [SNAKE])
        self.assertEqual((names(a), names(b)), ([], []))
        trampler = creature("Trampler", 5, 5, "Trample, deathtouch")
        game, a, b = fight([trampler], [OGRE])
        self.assertEqual((b.life, names(b)), (36, []))  # one damage is lethal, four trample over

    def test_first_strike_kills_before_damage_back(self):
        game, a, b = fight([KNIGHT], [BEAR])
        self.assertEqual((names(a), names(b)), (["Knight"], []))

    def test_double_strike(self):
        game, a, b = fight([DOUBLE])
        self.assertEqual(b.life, 36)

    def test_lifelink(self):
        game, a, b = fight([PRIEST])
        self.assertEqual((a.life, b.life), (42, 38))

    def test_blocked_creature_stays_blocked_if_blocker_leaves(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(OGRE)]
        b.battlefield = [Permanent(BEAR)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.destroy(b.battlefield[0])
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(b.life, 40)


class CommanderDamageTests(unittest.TestCase):
    def test_21_commander_damage_loses(self):
        game, _, _ = table(attack_all)
        a, b = game.seats
        titan = creature("Titan", 7, 7)
        a.commander_names = {"Titan"}
        a.battlefield = [Permanent(titan)]
        b.commander_damage[(0, "Titan")] = 14
        game.combat.declare_attackers(a)
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        self.assertEqual(b.life, 33)
        self.assertTrue(b.lost)

    def test_only_commanders_count(self):
        game, a, b = fight([OGRE])
        self.assertEqual(b.commander_damage, {})


class TurnTests(unittest.TestCase):
    def test_first_strike_damage_step_has_priority(self):
        game, a_player, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(KNIGHT)]
        game.turn = 3
        game._take_turn(a)
        steps = [p for p, _ in a_player.prompts if p.startswith("Priority")]
        self.assertIn("Priority: first_strike_damage", steps)
        self.assertEqual(game.seats[1].life, 38)

    def test_bots_finish_games(self):
        forest = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
        bear = Card(name="Grizzly Bears", mana_cost="{1}{G}", type_line="Creature — Bear", power="2", toughness="2")
        commander = Card(name="Omnath", mana_cost="{2}{G}", type_line="Legendary Creature — Elemental",
                         power="4", toughness="4")
        green = Deck([commander], [forest] * 38 + [bear] * 61, [])
        bots = [BotPlayer(f"P{i}", green) for i in range(4)]
        winner = Game([(b, green) for b in bots], seed=7).play(max_turns=200)
        self.assertIsNotNone(winner)


if __name__ == "__main__":
    unittest.main()
