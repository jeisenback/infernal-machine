import unittest

from infernal_machine.cards import Card
from infernal_machine.characteristics import Modifier
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, attack_all
from tests.test_effects import BOLT, MURDER, lands, pick, table

GROWTH = Card(name="Giant Growth", mana_cost="{G}", type_line="Instant", oracle_text="Target creature gets +3/+3 until end of turn.")
WINGS = Card(name="Wings", mana_cost="{U}", type_line="Instant",
             oracle_text="Target creature gets +1/+0 and gains flying until end of turn.")
WEAKEN = Card(name="Disfigure", mana_cost="{B}", type_line="Instant",
              oracle_text="Target creature gets −2/−2 until end of turn.")
OVERRUN = Card(name="Overrun", mana_cost="{G}", type_line="Sorcery",
               oracle_text="Creatures you control get +3/+3 and gain trample until end of turn.")
PROTECT = Card(name="Protect", mana_cost="{G}", type_line="Instant",
               oracle_text="Target creature you control gains hexproof and indestructible until end of turn.")
DRAGON = Card(name="Shivan Dragon", mana_cost="{R}", type_line="Creature — Dragon", power="5", toughness="5",
              oracle_text="Flying\n{R}: Shivan Dragon gets +1/+0 until end of turn.")
ANTHEM = Card(name="Glorious Anthem", mana_cost="{W}", type_line="Enchantment", oracle_text="Creatures you control get +1/+1.")
LORD = Card(name="Elvish Archdruid", mana_cost="{G}", type_line="Creature — Elf Druid", power="2", toughness="2",
            oracle_text="Other Elf creatures you control get +1/+1.")
ELF = Card(name="Elf", mana_cost="{G}", type_line="Creature — Elf Warrior", power="1", toughness="1")
HASTE = Card(name="Fervor", mana_cost="{R}", type_line="Enchantment", oracle_text="Creatures you control have haste.")


class ModifierTests(unittest.TestCase):
    def test_pump_until_end_of_turn(self):
        game, _, _ = table(pick(CAST, "Bear"))
        game.seats[0].hand = [GROWTH]
        game.seats[0].battlefield = lands(1) + [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        bear = game.seats[0].battlefield[-1]
        self.assertEqual((game.power(bear), game.toughness(bear)), (5, 5))
        game.step = "cleanup"
        game._turn_based_actions(game.seats[0])
        self.assertEqual((game.power(bear), game.toughness(bear)), (2, 2))

    def test_pump_saves_from_bolt(self):
        # A bolts B's Bear; B responds with Giant Growth.
        game, _, b = table(pick(CAST, "Bear"))
        b.policy = lambda p, o: pick(CAST, "Bear")(p, o) if game.stack or p.startswith("Choose") else o.index("Pass")
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1)
        game.seats[1].hand = [GROWTH]
        game.seats[1].battlefield = lands(1) + [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].battlefield[-1].card, BEAR)

    def test_minus_until_end_of_turn_kills(self):
        game, _, _ = table(pick(CAST, "Bear"))
        game.seats[0].hand = [WEAKEN]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].graveyard, [BEAR])

    def test_granted_flying_matters_in_combat(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        b.battlefield = [Permanent(BEAR)]
        game.modify_until_end_of_turn(bear, Modifier(1, 0, frozenset({"flying"})))
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(b.life, 37)  # unblockable by a non-flyer, and 3 power

    def test_overrun_affects_creatures_present_on_resolution(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [OVERRUN]
        seat.battlefield = lands(1) + [Permanent(BEAR), Permanent(BEAR)]
        game._priority_round(seat)
        later = Permanent(BEAR)
        seat.battlefield.append(later)
        self.assertEqual([game.power(p) for p in seat.battlefield[1:]], [5, 5, 2])
        self.assertTrue(game.has_keyword(seat.battlefield[1], "trample"))

    def test_granted_hexproof_and_indestructible(self):
        game, _, _ = table(None, pick(CAST, "Bear"))
        bear = Permanent(BEAR)
        game.seats[1].battlefield = [bear]
        game.modify_until_end_of_turn(bear, Modifier(keywords=frozenset({"hexproof", "indestructible"})))
        self.assertEqual(game.target_options("creature", game.seats[0]), [])
        game.destroy(bear)
        self.assertEqual(game.seats[1].battlefield, [bear])

    def test_firebreathing(self):
        game, _, _ = table(pick(ACTIVATE + "Shivan"))
        dragon = Permanent(DRAGON)
        game.seats[0].battlefield = [dragon] + lands(3)
        game._priority_round(game.seats[0])  # pump with every land (the bot-style policy repeats)
        self.assertEqual(game.power(dragon), 8)

    def test_anthem_and_lord(self):
        game, _, _ = table()
        seat = game.seats[0]
        lord, elf, bear = Permanent(LORD), Permanent(ELF), Permanent(BEAR)
        seat.battlefield = [Permanent(ANTHEM), lord, elf, bear]
        game.seats[1].battlefield = [Permanent(BEAR)]
        self.assertEqual([game.power(p) for p in (lord, elf, bear)], [3, 3, 3])  # lord doesn't pump itself
        self.assertEqual(game.power(game.seats[1].battlefield[0]), 2)  # "you control" only
        self.assertEqual(game.label(elf), "Elf 3/3 (seat 0, #3)")

    def test_anthem_goes_away_with_its_source(self):
        game, _, _ = table(pick(CAST, "Glorious"))
        seat = game.seats[0]
        anthem = Permanent(ANTHEM)
        seat.battlefield = [anthem, Permanent(BEAR)] + lands(3)
        game.seats[0].hand = [Card(name="Disenchant", mana_cost="{1}{W}", type_line="Instant",
                                   oracle_text="Destroy target artifact or enchantment.")]
        game._priority_round(seat)
        self.assertEqual(game.power(seat.battlefield[0]), 2)

    def test_static_haste(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(HASTE), Permanent(BEAR, sick=True)]
        game.combat.declare_attackers(a)
        self.assertEqual(len(game.combat.attacks), 1)

    def test_lord_dying_shrinks_the_team_mid_combat(self):
        game, _, _ = table(pick(CAST, "Elvish"))
        seat = game.seats[0]
        seat.hand = [MURDER]
        seat.battlefield = lands(3)
        elf = Permanent(ELF, damage=1)
        game.seats[1].battlefield = [Permanent(LORD), elf]
        game._priority_round(seat)
        self.assertEqual(game.seats[1].battlefield, [])  # the 2/2 elf with 1 damage dies once it's a 1/1

    def test_swords_uses_power_including_modifiers(self):
        from tests.test_exile import SWORDS
        game, _, _ = table(pick(CAST, "Bear"))
        game.seats[0].hand = [SWORDS]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(ANTHEM), Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].life, 43)

    def test_report(self):
        for card in (GROWTH, WINGS, WEAKEN, OVERRUN, PROTECT, DRAGON, ANTHEM, LORD, HASTE):
            self.assertEqual(unsupported_lines(card), [], card.name)


if __name__ == "__main__":
    unittest.main()
