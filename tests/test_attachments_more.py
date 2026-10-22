import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import ReturnSelfToHand, activated_abilities, granted_abilities, granted_mana, triggered_abilities
from infernal_machine.game import PASS, Permanent
from infernal_machine.mana import parse_cost
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.helpers import BEAR, FOREST, run_stack, table3

BLOOD_SWORD = Card(name="Blood Sword", mana_cost="{2}", type_line="Artifact — Equipment",
                   oracle_text="Equipped creature gets +2/+2.\nEquip—Pay 3 life.")
GRIM_SWORD = Card(name="Grim Sword", mana_cost="{2}", type_line="Artifact — Equipment",
                  oracle_text="Equipped creature gets +3/+3.\nEquip—Sacrifice a creature.")
LIFE_SWORD = Card(name="Sword of Life", mana_cost="{3}", type_line="Artifact — Equipment",
                  oracle_text="Equipped creature gets +2/+2.\nWhenever equipped creature deals combat damage to a player, "
                              "you gain 3 life.\nEquip {2}")
HEIRLOOM = Card(name="Heirloom", mana_cost="{1}", type_line="Artifact — Equipment",
                oracle_text="Whenever equipped creature dies, draw a card.\nEquip {1}")
RANCOR = REAL["Rancor"]
LOYALTY = Card(name="Loyal Aura", mana_cost="{1}", type_line="Enchantment — Aura",
               oracle_text="Enchant creature\nEnchanted creature gets +1/+1.\nWhen enchanted creature dies, return Loyal "
                           "Aura to its owner's hand.")
SEEDS = Card(name="Fertile Aura", mana_cost="{1}", type_line="Enchantment — Aura",
             oracle_text="Enchant land\nEnchanted land has \"{T}: Add {G}{G}.\"")
WELLSPRING = Card(name="Wellspring Aura", mana_cost="{1}", type_line="Enchantment — Aura",
                  oracle_text="Enchant creature\nEnchanted creature has \"{T}: Draw a card.\"")


def activations(game, seat, text):
    return [a for a in game._activations(seat, True) if text in a]


class EquipCostTests(unittest.TestCase):
    def test_parse(self):
        [ability] = activated_abilities(BLOOD_SWORD)
        self.assertEqual((ability.life, ability.mana_cost, ability.sorcery_speed), (3, "", True))
        [ability] = activated_abilities(GRIM_SWORD)
        self.assertEqual((ability.sacrifice_other, ability.sacrifice_another), ("creature", False))
        self.assertEqual(unsupported_lines(BLOOD_SWORD) + unsupported_lines(GRIM_SWORD), [])

    def test_paying_life_to_equip(self):
        game, _ = table3()
        a = game.seats[0]
        equipment, bear = Permanent(BLOOD_SWORD), Permanent(BEAR)
        a.battlefield = [equipment, bear]
        [action] = activations(game, a, "Equip")
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((a.life, equipment.attached_to is bear), (37, True))

    def test_not_offered_when_it_would_kill(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.life = [Permanent(BLOOD_SWORD), Permanent(BEAR)], 2
        self.assertEqual(activations(game, a, "Equip"), [])

    def test_sacrificing_a_creature_to_equip(self):
        game, _ = table3()
        a = game.seats[0]
        fodder, keeper = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [Permanent(GRIM_SWORD), fodder, keeper]
        [action] = activations(game, a, "Equip")
        game._perform(a, action)
        self.assertEqual(len([p for p in a.battlefield if "Creature" in p.card.type_line]), 1)

    def test_nothing_to_sacrifice(self):
        game, _ = table3()
        game.seats[0].battlefield = [Permanent(GRIM_SWORD)]
        self.assertEqual(activations(game, game.seats[0], "Equip"), [])

    def test_bots_equip_for_a_life_cost(self):
        bot = BotPlayer("A", Deck([FOREST], [BLOOD_SWORD], []))
        options = [PASS, "Activate: Blood Sword (seat 0, #1): Equip—Pay 3 life."]
        self.assertEqual(bot.choose("Priority: main1", options), 1)


class HostTriggerTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual([t.event for t in triggered_abilities(LIFE_SWORD)], ["host_combat_damage"])
        self.assertEqual([t.event for t in triggered_abilities(HEIRLOOM)], ["host_dies"])
        self.assertEqual([t.event for t in triggered_abilities(RANCOR)], ["put_into_graveyard"])
        self.assertEqual([t.event for t in triggered_abilities(LOYALTY)], ["host_dies"])
        for card in (LIFE_SWORD, HEIRLOOM, RANCOR, LOYALTY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_equipped_creature_deals_combat_damage_to_a_player(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        sword = Permanent(LIFE_SWORD, attached_to=bear)
        a.battlefield = [bear, sword]
        game.damage(b, 4, bear, combat=True)
        run_stack(game)
        self.assertEqual(a.life, 43)

    def test_not_for_other_creatures_or_noncombat_damage(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear, other = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [bear, other, Permanent(LIFE_SWORD, attached_to=bear)]
        game.damage(b, 2, other, combat=True)
        game.damage(b, 2, bear)
        run_stack(game)
        self.assertEqual(a.life, 40)

    def test_when_the_equipped_creature_dies(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 3
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(HEIRLOOM, attached_to=bear)]
        game._leave_battlefield(bear, "dies")
        run_stack(game)
        self.assertEqual(len(a.hand), 1)


class ReturnToHandTests(unittest.TestCase):
    def test_rancor_returns_when_its_creature_dies(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        rancor = Permanent(RANCOR, attached_to=bear)
        a.battlefield = [bear, rancor]
        game._leave_battlefield(bear, "dies")
        game._check_state()  # the Aura is no longer attached to anything
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Rancor"], ["Bear"]))
        self.assertEqual(a.battlefield, [])

    def test_rancor_returns_when_destroyed_itself(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        rancor = Permanent(RANCOR, attached_to=bear)
        a.battlefield = [bear, rancor]
        game.destroy(rancor)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], len(a.battlefield)), (["Rancor"], 1))

    def test_exiled_it_stays_gone(self):
        game, _ = table3()
        a = game.seats[0]
        rancor = Permanent(RANCOR, attached_to=Permanent(BEAR))
        a.battlefield = [rancor]
        game.exile(rancor)
        run_stack(game)
        self.assertEqual((a.hand, [c.name for c in a.exile]), ([], ["Rancor"]))

    def test_the_enchanted_creature_dying_wording(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(LOYALTY, attached_to=bear)]
        game._leave_battlefield(bear, "dies")
        game._check_state()
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Loyal Aura"])

    def test_the_effect_is_the_dead_source(self):
        self.assertEqual(triggered_abilities(RANCOR)[0].effects, (ReturnSelfToHand(),))


class GrantedAbilityTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual([a.text for a in granted_abilities(WELLSPRING)], ["{T}: Draw a card."])
        self.assertEqual(granted_mana(SEEDS), [frozenset("G"), frozenset("G")])
        self.assertEqual(unsupported_lines(SEEDS) + unsupported_lines(WELLSPRING), [])
        bad = Card(name="Bad", mana_cost="{1}", type_line="Enchantment — Aura",
                   oracle_text="Enchant creature\nEnchanted creature has \"{T}: Do something strange.\"")
        self.assertEqual(len(unsupported_lines(bad)), 1)

    def test_the_enchanted_creature_can_use_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 3
        host, other = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [host, other, Permanent(WELLSPRING, attached_to=host)]
        actions = activations(game, a, "Draw a card")
        self.assertEqual(len(actions), 1)
        self.assertIn("(seat 0, #1)", actions[0])  # the host, not the other Bear
        game._perform(a, actions[0])
        run_stack(game)
        self.assertEqual((len(a.hand), host.tapped), (1, True))
        self.assertEqual(activations(game, a, "Draw a card"), [])

    def test_a_summoning_sick_creature_cannot_tap(self):
        game, _ = table3()
        a = game.seats[0]
        host = Permanent(BEAR, sick=True)
        a.battlefield = [host, Permanent(WELLSPRING, attached_to=host)]
        self.assertEqual(activations(game, a, "Draw a card"), [])

    def test_the_ability_goes_when_the_aura_does(self):
        game, _ = table3()
        a = game.seats[0]
        host = Permanent(BEAR)
        aura = Permanent(WELLSPRING, attached_to=host)
        a.battlefield = [host, aura]
        a.battlefield.remove(aura)
        self.assertEqual(activations(game, a, "Draw a card"), [])

    def test_an_enchanted_land_makes_more_mana(self):
        game, _ = table3()
        a = game.seats[0]
        land = Permanent(FOREST)
        a.battlefield = [land]
        self.assertIsNone(game._pay_cost(a, parse_cost("{G}{G}")))
        a.battlefield.append(Permanent(SEEDS, attached_to=land))
        self.assertEqual(game._pay_cost(a, parse_cost("{G}{G}")), [land])
