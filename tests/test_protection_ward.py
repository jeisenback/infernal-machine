import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.characteristics import Modifier
from infernal_machine.client import Narrator
from infernal_machine.effects import Pump, attached_abilities, printed_protection, spell_effects, ward_cost
from infernal_machine.game import ACTIVATE, CAST, WARD_PROMPT, Game, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import attack_all
from tests.test_effects import lands, pick, table

RED, BLUE, GREEN = frozenset("R"), frozenset("U"), frozenset("G")


def creature(name, power, toughness, colors, text=""):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Test", power=str(power), toughness=str(toughness),
                colors=tuple(colors), oracle_text=text)


BOLT = Card(name="Lightning Bolt", mana_cost="{R}", type_line="Instant", colors=("R",),
            oracle_text="Lightning Bolt deals 3 damage to any target.")
DOOM = Card(name="Doom", mana_cost="{R}", type_line="Instant", colors=("R",), oracle_text="Destroy target creature.")
PYROCLASM = Card(name="Pyroclasm", mana_cost="{1}{R}", type_line="Sorcery", colors=("R",),
                 oracle_text="Pyroclasm deals 2 damage to each creature.")
KNIGHT = creature("Knight", 3, 3, "W", "Protection from red")
PALADIN = creature("Paladin", 2, 2, "W", "Flying, protection from red and from blue")
RED_OGRE = creature("Red Ogre", 3, 3, "R")
RED_GOBLIN = creature("Red Goblin", 1, 1, "R")
GREEN_BEAR = creature("Green Bear", 2, 2, "G")
PLAIN = creature("Plain Bear", 2, 2, "G")
WARDED = creature("Warded Bear", 2, 2, "G", "Ward {2}")
SWORD = Card(name="Sword of Fire and Ice", mana_cost="{3}", type_line="Artifact — Equipment",
             oracle_text="Equipped creature gets +2/+2 and has protection from red and from blue.\nEquip {2}")
RED_AURA = Card(name="Red Aura", mana_cost="{R}", type_line="Enchantment — Aura", colors=("R",),
                oracle_text="Enchant creature\nEnchanted creature gets +1/+0.")
RED_EQUIPMENT = Card(name="Red Blade", mana_cost="{1}", type_line="Artifact — Equipment", colors=("R",),
                     oracle_text="Equipped creature gets +1/+1.\nEquip {1}")
SORCERER = Card(name="Prodigal Sorcerer", mana_cost="{2}{U}", type_line="Creature — Human Wizard", power="1", toughness="1",
                oracle_text="{T}: Prodigal Sorcerer deals 1 damage to any target.")


def table2(*policies):
    """table() with the players in a list, like table3()."""
    game, a, b = table(*policies)
    return game, [a, b]


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class ParseTests(unittest.TestCase):
    def test_protection(self):
        self.assertEqual(printed_protection(KNIGHT), frozenset("R"))
        self.assertEqual(printed_protection(PALADIN), frozenset("RU"))
        self.assertEqual(printed_protection(SWORD), frozenset())  # the Sword gives it, it doesn't have it
        self.assertEqual(printed_protection(RED_OGRE), frozenset())
        [buff] = attached_abilities(SWORD)
        self.assertEqual(buff.modifier, Modifier(2, 2, frozenset({"protection from red", "protection from blue"})))

    def test_granted_until_end_of_turn(self):
        [pump] = spell_effects(Card(name="Shield", oracle_text="Target creature gains protection from red until end of turn."))
        self.assertEqual(pump, Pump(Modifier(keywords=frozenset({"protection from red"})), "creature"))
        both = Card(name="Both", oracle_text="Target creature gets +1/+1 and gains flying and protection from green until end of turn.")
        self.assertEqual(spell_effects(both)[0].modifier.keywords, frozenset({"flying", "protection from green"}))
        choice = Card(name="Mother", oracle_text="Target creature gains protection from the color of your choice until end of turn.")
        self.assertIsNone(spell_effects(choice))

    def test_ward(self):
        self.assertEqual((ward_cost(WARDED), ward_cost(KNIGHT)), ("{2}", None))
        self.assertEqual(ward_cost(creature("x", 1, 1, "G", "Flying, ward {1}")), "{1}")
        self.assertIsNone(ward_cost(creature("x", 1, 1, "G", "Ward—Pay 3 life.")))

    def test_report(self):
        for card in (KNIGHT, PALADIN, WARDED, SWORD):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual(unsupported_lines(creature("x", 1, 1, "G", "Protection from everything")), ["Protection from everything"])
        self.assertEqual(unsupported_lines(creature("x", 1, 1, "G", "Ward—Pay 3 life.")), ["Ward—Pay 3 life."])


class ProtectionTests(unittest.TestCase):
    def test_cannot_be_targeted_by_the_color_but_by_others(self):
        game, _, _ = table()
        game.seats[1].battlefield = [Permanent(KNIGHT), Permanent(PLAIN)]
        by_red = [label for label, _ in game.target_options("creature", game.seats[0], RED)]
        self.assertEqual(by_red, ["Plain Bear 2/2 (seat 1, #2)"])
        self.assertEqual(len(game.target_options("creature", game.seats[0], BLUE)), 2)  # Knight isn't protected from blue
        self.assertEqual(len(game.target_options("creature", game.seats[0], frozenset())), 2)  # colorless sources ignore it

    def test_a_spell_whose_only_target_is_protected_cannot_be_cast(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(KNIGHT)]
        seat.hand = [DOOM]
        self.assertNotIn(CAST + "Doom", game.legal_actions(seat))
        seat.hand = [BOLT]
        self.assertIn(CAST + "Lightning Bolt", game.legal_actions(seat))  # "any target" still has the players

    def test_gaining_protection_in_response_makes_the_spell_fizzle(self):
        game, players = table2(pick(CAST, "Plain"))
        seat = game.seats[0]
        seat.hand = [BOLT]
        seat.battlefield = lands(1)
        plain = Permanent(PLAIN)
        game.seats[1].battlefield = [plain]
        game._perform(seat, CAST + "Lightning Bolt")
        game.modify_until_end_of_turn(plain, Modifier(keywords=frozenset({"protection from red"})))
        game._resolve(game.stack.pop())
        self.assertEqual(plain.damage, 0)
        self.assertTrue(any(e["event"] == "fizzle" for e in players[0].events))

    def test_damage_from_the_color_is_prevented(self):
        game, players = table2(pick(CAST))
        seat = game.seats[0]
        seat.hand = [PYROCLASM]
        seat.battlefield = lands(2)
        game.seats[1].battlefield = [Permanent(KNIGHT), Permanent(PLAIN)]
        game._priority_round(seat)
        self.assertEqual(names(game.seats[1]), ["Knight"])  # the Plain Bear died; Knight shrugged it off
        self.assertEqual(game.seats[1].battlefield[0].damage, 0)
        self.assertTrue(any(e["event"] == "damage_prevented" for e in players[0].events))

    def test_combat_damage_from_the_color_is_prevented(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(RED_OGRE)]
        b.battlefield = [Permanent(KNIGHT)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        self.assertEqual((names(a), names(b)), ([], ["Knight"]))  # the 3/3 Knight took nothing and killed the Ogre

    def test_cannot_be_blocked_by_the_color(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(KNIGHT)]  # protection from red
        b.battlefield = [Permanent(RED_GOBLIN), Permanent(GREEN_BEAR)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        self.assertEqual([p.card.name for p in game.combat.attacks[0].blockers], ["Green Bear"])

    def test_protection_from_two_colors_at_once(self):
        twice = creature("Twice Shielded", 2, 2, "W", "Protection from red and from blue")
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(twice)]
        b.battlefield = [Permanent(RED_GOBLIN), Permanent(creature("Blue Drake", 2, 2, "U")), Permanent(GREEN_BEAR)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        self.assertEqual([p.card.name for p in game.combat.attacks[0].blockers], ["Green Bear"])
        self.assertEqual(printed_protection(twice), frozenset("RU"))

    def test_equipment_grants_protection_and_attachments_of_that_color_fall_off(self):
        game, _, _ = table()
        seat = game.seats[0]
        bear = Permanent(PLAIN)
        sword = Permanent(SWORD, attached_to=bear)
        aura = Permanent(RED_AURA, attached_to=bear)
        blade = Permanent(RED_EQUIPMENT, attached_to=bear)
        seat.battlefield = [bear, sword, aura, blade]
        game._check_state()
        self.assertEqual([p.card.name for p in seat.battlefield], ["Plain Bear", "Sword of Fire and Ice", "Red Blade"])
        self.assertEqual((sword.attached_to, blade.attached_to), (bear, None))
        self.assertIn(RED_AURA, seat.graveyard)
        self.assertFalse(game.protected_from(sword, RED))  # the equipment doesn't protect itself

    def test_a_creature_keeps_attachments_of_other_colors(self):
        game, _, _ = table()
        bear = Permanent(PLAIN)
        green_aura = Permanent(Card(name="Vines", type_line="Enchantment — Aura", colors=("G",),
                                    oracle_text="Enchant creature\nEnchanted creature gets +1/+1."), attached_to=bear)
        game.seats[0].battlefield = [bear, Permanent(SWORD, attached_to=bear), green_aura]
        game._check_state()
        self.assertEqual(len(game.seats[0].battlefield), 3)


class WardTests(unittest.TestCase):
    def cast_at_warded(self, answer, lands_count=3):
        game, players = table2(pick(CAST, "Warded", answer))
        seat = game.seats[0]
        seat.hand = [BOLT]
        seat.battlefield = lands(lands_count)
        warded = Permanent(WARDED)
        game.seats[1].battlefield = [warded]
        game._priority_round(seat)
        return game, players, warded

    def test_paying_lets_the_spell_resolve(self):
        game, players, warded = self.cast_at_warded("Pay")
        self.assertEqual(game.seats[1].battlefield, [])  # 3 damage killed the 2/2
        self.assertTrue(all(p.tapped for p in game.seats[0].battlefield))
        prompts = [(p, o) for p, o in players[0].prompts if p.startswith(WARD_PROMPT)]
        self.assertEqual(prompts, [(WARD_PROMPT + "Lightning Bolt", ["Pay {2}", "Don't pay"])])
        self.assertTrue(any(e["event"] == "ward_paid" for e in players[0].events))

    def test_declining_counters_the_spell(self):
        game, players, warded = self.cast_at_warded("Don't")
        self.assertEqual((warded.damage, len(game.seats[1].battlefield)), (0, 1))
        self.assertEqual(game.seats[0].graveyard, [BOLT])
        self.assertEqual(game.stack, [])
        self.assertTrue(any(e["event"] == "countered" and e["card"] == "Lightning Bolt" for e in players[0].events))

    def test_not_being_able_to_pay_counters_without_asking(self):
        game, players, warded = self.cast_at_warded("Pay", lands_count=2)  # {R} for the Bolt leaves one land
        self.assertEqual((warded.damage, game.seats[0].graveyard), (0, [BOLT]))
        self.assertFalse(any(p.startswith(WARD_PROMPT) for p, _ in players[0].prompts))

    def test_your_own_permanents_are_not_warded_against_you(self):
        game, players = table2(None, pick(CAST, "Warded"))
        seat = game.seats[1]
        seat.hand = [BOLT]
        seat.battlefield = lands(1) + [Permanent(WARDED)]
        game.active = 1
        game._priority_round(seat)
        self.assertEqual([p.card.name for p in seat.battlefield if "Creature" in p.card.type_line], [])  # it died to the Bolt
        self.assertFalse(any(p.startswith(WARD_PROMPT) for p, _ in players[1].prompts))

    def test_ward_applies_to_activated_abilities(self):
        game, _ = self.ability_game(lands_count=2)
        self.assertEqual(game.seats[1].battlefield[0].damage, 1)
        game, players = self.ability_game(lands_count=0, answer="Don't")
        self.assertEqual(game.seats[1].battlefield[0].damage, 0)
        self.assertEqual(names(game.seats[0]), ["Prodigal Sorcerer"])  # countering the ability leaves its source alone
        self.assertEqual(game.seats[0].graveyard, [])
        self.assertTrue(any(e["event"] == "countered" and e.get("ability") for e in players[0].events))

    def ability_game(self, lands_count, answer="Pay"):
        game, players = table2(pick(ACTIVATE, "Warded", answer))
        seat = game.seats[0]
        seat.battlefield = [Permanent(SORCERER)] + lands(lands_count)
        game.seats[1].battlefield = [Permanent(WARDED)]
        game._priority_round(seat)
        return game, players

    def test_bots_pay_ward_when_they_can(self):
        bot = BotPlayer("A", Deck([KNIGHT], [WARDED], []))
        self.assertEqual(bot.choose(WARD_PROMPT + "Lightning Bolt", ["Pay {2}", "Don't pay"]), 0)


class NarratorTests(unittest.TestCase):
    def test_new_events_read_as_sentences(self):
        n = Narrator()
        n.me = 0
        n.names = {0: "Alice", 1: "Bob"}
        self.assertEqual(n.narrate({"event": "damage_prevented", "card": "Knight", "amount": 3}),
                         "Damage to Knight is prevented (protection).")
        self.assertEqual(n.narrate({"event": "ward_paid", "seat": 1, "card": "Warded Bear", "cost": "{2}"}),
                         "Bob pays the ward cost {2}.")
        self.assertEqual(n.narrate({"event": "countered", "seat": 0, "card": "Sorcerer", "ability": "{T}: x"}),
                         "Sorcerer's ability is countered.")


class GameTests(unittest.TestCase):
    def test_bot_games_with_protection_and_ward_finish(self):
        commander = Card(name="Omnath", mana_cost="{2}{G}", type_line="Legendary Creature — Elemental", power="4", toughness="4")
        rainbow = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG"))
        deck = Deck([commander], [rainbow] * 40 + [KNIGHT, PALADIN, WARDED, RED_OGRE, GREEN_BEAR, BOLT, DOOM, PYROCLASM, SWORD] * 6, [])
        for seed in range(5):
            bots = [BotPlayer(f"P{i}", deck) for i in range(4)]
            game = Game([(b, deck) for b in bots], seed=seed)
            self.assertIsNotNone(game.play(max_turns=200), f"seed {seed} had no winner")


if __name__ == "__main__":
    unittest.main()
