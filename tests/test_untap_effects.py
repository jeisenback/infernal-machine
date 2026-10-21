"""Untap effects (#209): Freed from the Real's "{U}: Untap enchanted creature.", Devoted Druid's "Put a -1/-1 counter on this creature:
Untap this creature." (a cost that puts a counter on the source) and Derevi, Empyrial Tactician (tap or untap target permanent when it
enters and whenever a creature you control deals combat damage to a player; put it onto the battlefield from the command zone). Each
card from its real Oracle text; the other creatures and lands are probes."""

import unittest

from infernal_machine.game import ACTIVATE, ACTIVATE_COMMAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, activate, enter, lands, names, pick, real, run_stack, table3

FREED = real("Freed from the Real", "{2}{U}", "Enchantment — Aura",
             "Enchant creature\n{U}: Tap enchanted creature.\n{U}: Untap enchanted creature.", colors=("U",))
DRUID = real("Devoted Druid", "{1}{G}", "Creature — Elf Druid", "{T}: Add {G}.\nPut a -1/-1 counter on this creature: Untap this creature.",
             "0", "2", colors=("G",))
DEREVI = real("Derevi, Empyrial Tactician", "{G}{W}{U}", "Legendary Creature — Bird Wizard",
              "Flying\nWhen Derevi enters and whenever a creature you control deals combat damage to a player, you may tap or untap target "
              "permanent.\n{1}{G}{W}{U}: Put Derevi onto the battlefield from the command zone.", "2", "3", colors=("G", "U", "W"))


def actions(game, seat, prefix):
    return [a for a in game.legal_actions(seat) if a.startswith(prefix)]


class ParseTests(unittest.TestCase):
    def test_every_line_is_read(self):
        for card in (FREED, DRUID, DEREVI):
            self.assertEqual(unsupported_lines(card), [], card.name)


class FreedFromTheRealTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(None)
        self.a = self.game.seats[0]
        self.druid, self.freed = Permanent(DRUID), Permanent(FREED)
        self.a.battlefield = [self.druid, self.freed] + lands(2)
        self.game.attach(self.freed, self.druid)

    def test_it_untaps_the_enchanted_creature(self):
        self.druid.tapped = True
        activate(self.game, self.a, "Untap enchanted creature")
        self.assertFalse(self.druid.tapped)

    def test_the_tap_ability_still_taps(self):
        activate(self.game, self.a, "Tap enchanted creature")
        self.assertTrue(self.druid.tapped)

    def test_without_mana_it_is_not_offered(self):
        self.a.battlefield = [self.druid, self.freed]
        self.assertFalse([a for a in actions(self.game, self.a, ACTIVATE) if "Untap enchanted creature" in a])


class DevotedDruidTests(unittest.TestCase):
    def test_the_cost_puts_a_counter_and_the_creature_untaps(self):
        game, _ = table3(None)
        a = game.seats[0]
        druid = Permanent(DRUID)
        a.battlefield = [druid]
        druid.tapped = True
        activate(game, a, "Put a -1/-1 counter")
        self.assertFalse(druid.tapped)
        self.assertEqual(druid.counters.get("-1/-1"), 1)
        self.assertEqual(game.toughness(druid), 1)

    def test_the_second_counter_kills_it(self):
        game, _ = table3(None)
        a = game.seats[0]
        druid = Permanent(DRUID)
        a.battlefield = [druid]
        activate(game, a, "Put a -1/-1 counter")
        activate(game, a, "Put a -1/-1 counter")
        game._check_state()
        self.assertNotIn("Devoted Druid", names(a))


class DereviTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(pick("Ogre", "Tap", "Yes"))
        self.a, self.b = self.game.seats[0], self.game.seats[1]
        self.ogre = Permanent(OGRE)
        self.b.battlefield = [self.ogre]

    def test_when_it_enters_it_may_tap_a_permanent(self):
        enter(self.game, self.a, DEREVI)
        run_stack(self.game)
        self.assertTrue(self.ogre.tapped)

    def test_combat_damage_by_a_creature_you_control_triggers_it_too(self):
        derevi = Permanent(DEREVI)
        self.a.battlefield = [derevi, bear := Permanent(BEAR)]
        self.game.trigger("ally_combat_damage", derevi, self.a, subject=bear)  # as combat does when the Bear deals damage
        run_stack(self.game)
        self.assertTrue(self.ogre.tapped)

    def test_from_the_command_zone_it_enters_without_being_cast(self):
        self.a.command_zone = [DEREVI]
        self.a.battlefield = lands(4)
        offered = actions(self.game, self.a, ACTIVATE_COMMAND)
        self.assertEqual(offered, [ACTIVATE_COMMAND + DEREVI.name])
        self.game._perform(self.a, offered[0])
        run_stack(self.game)
        self.assertIn(DEREVI.name, names(self.a))
        self.assertEqual(self.a.command_zone, [])
        self.assertEqual(self.a.commander_casts.get(DEREVI.name, 0), 0)  # not cast: no commander tax

    def test_not_offered_without_the_mana_or_from_the_battlefield(self):
        self.a.command_zone = [DEREVI]
        self.a.battlefield = lands(3)
        self.assertEqual(actions(self.game, self.a, ACTIVATE_COMMAND), [])
        self.a.command_zone = []
        self.a.battlefield = [Permanent(DEREVI)] + lands(4)
        self.assertFalse([a for a in actions(self.game, self.a, ACTIVATE) if "command zone" in a])


if __name__ == "__main__":
    unittest.main()
