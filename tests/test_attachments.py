import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import attached_abilities, aura_kind, equip_abilities
from infernal_machine.game import ACTIVATE, CAST, PASS, TARGET_PROMPT, Game, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, attack_all
from tests.test_effects import FOREST, lands, pick, table
from tests.test_exile import OGRE

BOOTS = Card(name="Swiftfoot Boots", mana_cost="{2}", type_line="Artifact — Equipment",
             oracle_text="Equipped creature has hexproof and haste.\nEquip {1}")
GREAVES = Card(name="Lightning Greaves", mana_cost="{2}", type_line="Artifact — Equipment",
               oracle_text="Equipped creature has haste and shroud.\nEquip {0}")
SWORD = Card(name="Sword", mana_cost="{3}", type_line="Artifact — Equipment",
             oracle_text="Equipped creature gets +2/+2 and has flying.\nEquip {2}")
PACIFISM = Card(name="Pacifism", mana_cost="{1}{W}", type_line="Enchantment — Aura",
                oracle_text="Enchant creature\nEnchanted creature can't attack or block.")
ARMOR = Card(name="Armor", mana_cost="{1}{W}", type_line="Enchantment — Aura",
             oracle_text="Enchant creature you control\nEnchanted creature gets +2/+2 and has vigilance.")
GROWTH = REAL["Wild Growth"]
def equip(game, seat, name):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and name in a and "Equip" in a]


class ParseTests(unittest.TestCase):
    def test_equipment_and_auras(self):
        self.assertEqual([a.mana_cost for a in equip_abilities(BOOTS)], ["{1}"])
        self.assertEqual([a.mana_cost for a in equip_abilities(GREAVES)], ["{0}"])
        self.assertEqual(equip_abilities(Card(name="x", oracle_text="Equip {2}\nEquip legendary creature {1}"))[1].effects[0].target,
                         "legendary creature you control")
        self.assertEqual(equip_abilities(Card(name="x", oracle_text="Equip\u2014Pay 3 life.")), ())
        self.assertEqual(attached_abilities(SWORD)[0].modifier.power, 2)
        self.assertEqual(aura_kind(PACIFISM), "creature")
        self.assertEqual(aura_kind(ARMOR), "creature you control")
        self.assertEqual(aura_kind(GROWTH), "land")
        self.assertIsNone(aura_kind(BOOTS))

    def test_report(self):
        for card in (BOOTS, GREAVES, SWORD, PACIFISM, ARMOR):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual(unsupported_lines(GROWTH), [])  # "Enchant land" is understood; nothing else is missing


class EquipTests(unittest.TestCase):
    def test_equip_at_sorcery_speed_on_your_creature_only(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(BOOTS), Permanent(BEAR)] + lands(1)
        game.seats[1].battlefield = [Permanent(OGRE)]
        self.assertEqual(len(equip(game, seat, "Swiftfoot")), 1)
        self.assertEqual([label for label, _ in game.target_options("creature you control", seat)],
                         ["Bear 2/2 (seat 0, #2)"])
        game.step = "beginning_of_combat"
        self.assertEqual(equip(game, seat, "Swiftfoot"), [])

    def test_equipping_grants_keywords_and_stats(self):
        game, _, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        bear = Permanent(BEAR, sick=True)
        seat.battlefield = [Permanent(SWORD), bear] + lands(2)
        game._priority_round(seat)
        self.assertEqual((game.power(bear), game.toughness(bear)), (4, 4))
        self.assertTrue(game.has_keyword(bear, "flying"))
        self.assertEqual(game.label(seat.battlefield[0]), "Sword attached to Bear (seat 0, #1)")

    def test_boots_give_haste_and_hexproof(self):
        game, _, _ = table(attack_all)
        a, b = game.seats
        bear = Permanent(BEAR, sick=True)
        boots = Permanent(BOOTS, attached_to=bear)
        a.battlefield = [boots, bear]
        game.combat.declare_attackers(a)
        self.assertEqual(len(game.combat.attacks), 1)  # haste
        self.assertEqual(game.target_options("creature", b), [])  # hexproof vs opponents
        self.assertEqual(len(game.target_options("creature", a)), 1)  # but not vs its controller

    def test_greaves_shroud_and_free_equip(self):
        game, _, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        bear = Permanent(BEAR)
        seat.battlefield = [Permanent(GREAVES), bear]  # no lands at all: Equip {0}
        game._priority_round(seat)
        self.assertTrue(game.has_keyword(bear, "shroud"))
        self.assertEqual(game.target_options("creature", seat), [])  # not even its controller can target it

    def test_reequip_moves_it(self):
        game, _, _ = table(pick(ACTIVATE, "Ogre"))
        seat = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        boots = Permanent(SWORD, attached_to=bear)
        seat.battlefield = [boots, bear, ogre] + lands(2)
        game._priority_round(seat)
        self.assertIs(boots.attached_to, ogre)
        self.assertEqual((game.power(bear), game.power(ogre)), (2, 5))

    def test_equipment_stays_when_the_creature_dies(self):
        game, _, _ = table()
        seat = game.seats[0]
        bear = Permanent(BEAR)
        sword = Permanent(SWORD, attached_to=bear)
        seat.battlefield = [sword, bear]
        game.destroy(bear)
        game._check_state()
        self.assertEqual((seat.battlefield[0], sword.attached_to), (sword, None))

    def test_equip_fizzles_if_the_creature_is_gone(self):
        game, _, _ = table()
        seat = game.seats[0]
        bear, sword = Permanent(BEAR), Permanent(SWORD)
        seat.battlefield = [sword, bear] + lands(2)
        actions = equip(game, seat, "Sword")
        seat.player.policy = lambda prompt, options: options.index(actions[0]) if prompt.startswith("Priority") and actions[0] in options else 0
        game._perform(seat, actions[0])  # equip goes on the stack targeting the Bear
        game.destroy(bear)
        game._resolve(game.stack.pop())
        self.assertIsNone(sword.attached_to)


class AuraTests(unittest.TestCase):
    def test_pacifism(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        game.seats[0].hand = [PACIFISM]
        game.seats[0].battlefield = lands(2)
        ogre = Permanent(OGRE)
        game.seats[1].battlefield = [ogre]
        game._priority_round(game.seats[0])
        aura = game.seats[0].battlefield[-1]
        self.assertEqual((aura.card, aura.attached_to), (PACIFISM, ogre))
        game.seats[1].player.policy = attack_all
        game.active = 1
        game.combat.declare_attackers(game.seats[1])
        self.assertEqual(game.combat.attacks, [])  # can't attack
        game.combat.attacks = []
        game.active = 0
        game.seats[0].battlefield.append(Permanent(BEAR))  # keep the Aura on the battlefield
        game.seats[0].player.policy = attack_all
        game.combat.declare_attackers(game.seats[0])
        game.combat.declare_blockers()
        self.assertEqual(game.combat.attacks[0].blockers, [])  # can't block

    def test_aura_goes_to_the_graveyard_when_its_creature_leaves(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        game.seats[0].hand = [PACIFISM]
        game.seats[0].battlefield = lands(2)
        ogre = Permanent(OGRE)
        game.seats[1].battlefield = [ogre]
        game._priority_round(game.seats[0])
        game.destroy(ogre)
        game._check_state()
        self.assertEqual([p.card.name for p in game.seats[0].battlefield], ["City of Brass"] * 2)
        self.assertEqual(PACIFISM, game.seats[0].graveyard[-1])

    def test_buff_aura(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [ARMOR]
        bear = Permanent(BEAR)
        seat.battlefield = lands(2) + [bear]
        game.seats[1].battlefield = [Permanent(OGRE)]
        self.assertEqual([label for label, _ in game.target_options("creature you control", seat)],
                         ["Bear 2/2 (seat 0, #3)"])
        game._priority_round(seat)
        self.assertEqual((game.power(bear), game.toughness(bear)), (4, 4))
        self.assertTrue(game.has_keyword(bear, "vigilance"))

    def test_aura_fizzles_if_its_target_is_gone(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [PACIFISM]
        seat.battlefield = lands(2)
        ogre = Permanent(OGRE)
        game.seats[1].battlefield = [ogre]
        seat.player.policy = lambda prompt, options: (0 if prompt.startswith("Choose a target") else options.index("Cast: Pacifism"))
        game._perform(seat, "Cast: Pacifism")
        game.destroy(ogre)
        game._resolve(game.stack.pop())
        self.assertEqual(seat.graveyard, [PACIFISM])
        self.assertFalse(any(p.card is PACIFISM for p in seat.battlefield))

    def test_no_creature_means_no_aura(self):
        game, _, _ = table()
        game.seats[0].hand = [PACIFISM]
        game.seats[0].battlefield = lands(2)
        self.assertEqual(game.legal_actions(game.seats[0]), [PASS])


class BotTests(unittest.TestCase):
    def test_bot_targets_auras_sensibly(self):
        deck = Deck([BEAR], [PACIFISM, ARMOR, FOREST], [])
        bot = BotPlayer("A", deck)
        bot.notify({"event": "seat", "seat": 0, "name": "A", "life": 40})
        options = ["Grizzly Bears 2/2 (seat 0, #1)", "Ogre 3/3 (seat 1, #1)"]
        self.assertEqual(bot.choose(TARGET_PROMPT + "Armor", options), 0)  # helps its own
        self.assertEqual(bot.choose(TARGET_PROMPT + "Pacifism", options), 1)  # hurts theirs

    def test_bot_equips_once_and_does_not_loop(self):
        deck = Deck([BEAR], [FOREST] * 30 + [GREAVES, BOOTS, SWORD] * 3 + [BEAR] * 10, [])
        bots = [BotPlayer(f"P{i}", deck) for i in range(3)]
        game = Game([(b, deck) for b in bots], seed=5)
        winner = game.play(max_turns=200)
        self.assertLess(game.turn, 200)  # a {0} equip over and over would never finish
        self.assertIsNotNone(winner)


if __name__ == "__main__":
    unittest.main()
