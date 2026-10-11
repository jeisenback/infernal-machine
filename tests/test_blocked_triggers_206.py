"""Being blocked and blocking (#206): Bushido, Afflict, Rampage, "Whenever this creature becomes blocked ...", "blocks or becomes
blocked", and "This creature must be blocked if able", each from the card's own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import attack_all
from tests.test_effects import table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack


def creature(name, text="", power=2, toughness=2):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Bear", oracle_text=text, power=str(power), toughness=str(toughness))


def last(prompt, options):
    return len(options) - 1


def decline(prompt, options):
    return 0  # "Don't block" is the first option


def combat(attackers, blockers, blocker_policy=last):
    """Declare attackers and blockers, then let the triggers resolve; returns the game, the attackers' and the blockers' permanents."""
    game, _, _ = table(attack_all, blocker_policy)
    a, b = game.seats
    a.battlefield = [Permanent(c) for c in attackers]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    run_stack(game)
    return game, a, b


def size(game, permanent):
    return game.power(permanent), game.toughness(permanent)


class BushidoTests(unittest.TestCase):
    BUSHIDO = "Bushido 2 (Whenever this creature blocks or becomes blocked, it gets +2/+2 until end of turn.)"

    def test_a_blocked_attacker_gets_the_bonus(self):
        game, a, b = combat([creature("Samurai", self.BUSHIDO)], [creature("Bear")])
        self.assertEqual(size(game, a.battlefield[0]), (4, 4))

    def test_a_blocker_gets_the_bonus(self):
        game, a, b = combat([creature("Plain")], [creature("Samurai", self.BUSHIDO)])
        self.assertEqual(size(game, b.battlefield[0]), (4, 4))

    def test_an_unblocked_samurai_does_not(self):
        game, a, b = combat([creature("Samurai", self.BUSHIDO)], [])
        self.assertEqual(size(game, a.battlefield[0]), (2, 2))

    def test_a_samurai_that_does_not_block_does_not(self):
        game, a, b = combat([creature("Plain")], [creature("Samurai", self.BUSHIDO)], blocker_policy=decline)
        self.assertEqual(size(game, b.battlefield[0]), (2, 2))


class AfflictTests(unittest.TestCase):
    AFFLICT = "Afflict 3 (Whenever this creature becomes blocked, defending player loses 3 life.)"

    def test_being_blocked_costs_the_defender_life(self):
        game, a, b = combat([creature("Ammit", self.AFFLICT)], [creature("Bear")])
        self.assertEqual(b.life, 37)

    def test_not_being_blocked_does_not(self):
        game, a, b = combat([creature("Ammit", self.AFFLICT)], [])
        self.assertEqual(b.life, 40)


class RampageTests(unittest.TestCase):
    RAMPAGE = "Rampage 2 (Whenever this creature becomes blocked, it gets +2/+2 until end of turn for each creature blocking it beyond the first.)"

    def test_each_blocker_past_the_first_adds_the_bonus(self):
        game, a, b = combat([creature("Rampager", self.RAMPAGE)], [creature("A"), creature("B"), creature("C")])
        self.assertEqual(size(game, a.battlefield[0]), (6, 6))  # two extra blockers

    def test_one_blocker_adds_nothing(self):
        game, a, b = combat([creature("Rampager", self.RAMPAGE)], [creature("A")])
        self.assertEqual(size(game, a.battlefield[0]), (2, 2))


class TextTriggerTests(unittest.TestCase):
    def test_whenever_this_creature_becomes_blocked(self):
        tiger = creature("Troll", "Whenever this creature becomes blocked, it gets +1/+1 until end of turn.")
        game, a, b = combat([tiger], [creature("Bear")])
        self.assertEqual(size(game, a.battlefield[0]), (3, 3))
        game, a, b = combat([tiger], [])
        self.assertEqual(size(game, a.battlefield[0]), (2, 2))

    def test_blocks_or_becomes_blocked_works_both_ways(self):
        wagg = creature("Brushwagg", "Whenever this creature blocks or becomes blocked, it gets -2/+2 until end of turn.")
        game, a, b = combat([wagg], [creature("Bear")])
        self.assertEqual(size(game, a.battlefield[0]), (0, 4))
        game, a, b = combat([creature("Plain")], [wagg])
        self.assertEqual(size(game, b.battlefield[0]), (0, 4))


class MustBeBlockedTests(unittest.TestCase):
    STALKER = creature("Canopy Stalker", "This creature must be blocked if able.", 3, 3)

    def blockers_of(self, game):
        return [[p.card.name for p in attack.blockers] for attack in game.combat.attacks]

    def test_a_lone_creature_that_can_block_it_must(self):
        game, a, b = combat([self.STALKER], [creature("Bear")], blocker_policy=decline)
        self.assertEqual(self.blockers_of(game), [["Bear"]])

    def test_the_defender_chooses_which_of_several_blocks_it(self):
        asked = []

        def policy(prompt, options):
            if prompt.startswith("Choose a creature that blocks"):
                asked.append(options)
                return len(options) - 1
            return 0  # everyone else stays home

        game, a, b = combat([self.STALKER], [creature("A"), creature("B"), creature("C")], blocker_policy=policy)
        self.assertEqual([len(options) for options in asked], [3])
        self.assertEqual(self.blockers_of(game), [["C"]])

    def test_nothing_is_forced_if_nothing_can_block_it(self):
        flyer = creature("Flying Stalker", "Flying\nThis creature must be blocked if able.")
        game, a, b = combat([flyer], [creature("Bear")], blocker_policy=decline)
        self.assertEqual(self.blockers_of(game), [[]])

    def test_a_tapped_creature_does_not_have_to(self):
        tapped = Permanent(creature("Tapped"))
        tapped.tapped = True
        game, _, _ = table(attack_all, decline)
        a, b = game.seats
        a.battlefield = [Permanent(self.STALKER)]
        b.battlefield = [tapped]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        self.assertEqual(self.blockers_of(game), [[]])

    def test_a_creature_blocks_only_one_attacker(self):
        game, a, b = combat([self.STALKER, creature("Second Stalker", "This creature must be blocked if able.")], [creature("Bear")],
                            blocker_policy=last)  # asked about the second attacker too, it would take it
        self.assertEqual(sorted(len(x) for x in self.blockers_of(game)), [0, 1])

    def test_only_the_defending_player_has_to_block_it(self):
        def attacker_policy(prompt, options):
            seat = "seat 1" if prompt.endswith("Stalker (seat 0, #1)") or "First" in prompt else "seat 2"
            return next(i for i, o in enumerate(options) if seat in o)

        game, _ = table3(attacker_policy, decline, decline)
        a, b, c = game.seats
        a.battlefield = [Permanent(creature("First Stalker", "This creature must be blocked if able.")),
                         Permanent(creature("Second Stalker", "This creature must be blocked if able."))]
        b.battlefield, c.battlefield = [Permanent(creature("Bear B"))], [Permanent(creature("Bear C"))]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        by_attacker = {x.attacker.card.name: (x.defender.index, [p.card.name for p in x.blockers]) for x in game.combat.attacks}
        self.assertEqual(by_attacker, {"First Stalker": (1, ["Bear B"]), "Second Stalker": (2, ["Bear C"])})


class ReportTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for text in ("Bushido 2", "Afflict 3", "Rampage 1", "Flying, bushido 1", "This creature must be blocked if able.",
                     "Whenever this creature becomes blocked, it gets +1/+1 until end of turn.",
                     "Whenever this creature blocks or becomes blocked, it gets -2/+2 until end of turn."):
            with self.subTest(text):
                self.assertEqual(unsupported_lines(creature("Test", text)), [])


if __name__ == "__main__":
    unittest.main()
