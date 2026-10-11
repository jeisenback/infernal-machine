"""The five Station lands (the follow-up to #91): Adagia, Evendo, Kavaron, Susur Secundi and Uthros, each played from its
real Oracle text. Station taps another creature for charge counters equal to its power, at sorcery speed; the ability
marked "12+ |" works only with twelve or more charge counters on the land."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, CREW_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, real
from tests.test_triggers_80 import FOREST, PLAINS, RELIC, SHRINE

STATION = ("Station (Tap another creature you control: Put charge counters equal to its power on this Planet. "
           "Station only as a sorcery.)")


def planet(name, mana, ability):
    return Card(name=name, type_line="Land — Planet", produced_mana=(mana,),
                oracle_text=f"This land enters tapped.\n{{T}}: Add {{{mana}}}.\n{STATION}\n12+ | {ability}")


ADAGIA = planet("Adagia, Windswept Bastion", "W", "{3}{W}, {T}: Create a token that's a copy of target artifact or enchantment you control, "
                                                   "except it's legendary. Activate only as a sorcery.")
EVENDO = planet("Evendo, Waking Haven", "G", "{G}, {T}: Add {G} for each creature you control.")
KAVARON = planet("Kavaron, Memorial World", "R", "{1}{R}, {T}, Sacrifice a land: Create a 2/2 colorless Robot artifact creature token, "
                                                 "then creatures you control get +1/+0 and gain haste until end of turn.")
SUSUR = planet("Susur Secundi, Void Altar", "B", "{1}{B}, {T}, Pay 2 life, Sacrifice a creature: Draw cards equal to the sacrificed "
                                                 "creature's power. Activate only as a sorcery.")
UTHROS = planet("Uthros, Titanic Godcore", "U", "{U}, {T}: Add {U} for each artifact you control.")
ALL = [ADAGIA, EVENDO, KAVARON, SUSUR, UTHROS]
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
BIG = creature("Big", 7, 7)
SMALL = creature("Small", 1, 1)


def land(card, counters=0, tapped=False):
    permanent = Permanent(card, tapped=tapped)
    if counters:
        permanent.counters["charge"] = counters
    return permanent


def table(planet_permanent, others=(), theirs=(), policy=None, step="main1"):
    game, _ = table3(policy or pick())
    a = game.seats[0]
    a.battlefield = [planet_permanent, *others]
    game.seats[1].battlefield = list(theirs)
    game.active, game.step = 0, step
    return game, a


def actions(game, seat, fragment):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and fragment in x]


def activate(game, seat, fragment):
    game._perform(seat, actions(game, seat, fragment)[0])
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_all_five_are_fully_understood(self):
        for card in ALL:
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])


class StationTests(unittest.TestCase):
    def test_tapping_a_creature_puts_charge_counters_equal_to_its_power(self):
        for card in ALL:
            with self.subTest(card=card.name):
                permanent = land(card)
                game, a = table(permanent, [Permanent(OGRE)])
                activate(game, a, "Station")
                self.assertEqual(permanent.counters, {"charge": 3})
                self.assertTrue(a.battlefield[1].tapped)

    def test_you_choose_which_creature_to_tap(self):
        permanent = land(EVENDO)
        game, a = table(permanent, [Permanent(SMALL), Permanent(BIG)], policy=pick("Big"))
        activate(game, a, "Station")
        self.assertEqual(permanent.counters, {"charge": 7})
        self.assertEqual([p.tapped for p in a.battlefield[1:]], [False, True])

    def test_the_prompt_lists_the_creatures(self):
        seen = []

        def policy(prompt, options):
            seen.append((prompt, options))
            return 0

        game, a = table(land(EVENDO), [Permanent(SMALL), Permanent(BIG)], policy=policy)
        activate(game, a, "Station")
        self.assertEqual(seen[0][0], CREW_PROMPT + "Evendo, Waking Haven")
        self.assertEqual(len(seen[0][1]), 2)

    def test_counters_add_up_over_several_stations(self):
        permanent = land(EVENDO, 5)
        game, a = table(permanent, [Permanent(BIG)])
        activate(game, a, "Station")
        self.assertEqual(permanent.counters, {"charge": 12})

    def test_it_needs_another_untapped_creature(self):
        game, a = table(land(EVENDO), [])
        self.assertEqual(actions(game, a, "Station"), [], "no creature")
        tapped = Permanent(BEAR, tapped=True)
        game, a = table(land(EVENDO), [tapped])
        self.assertEqual(actions(game, a, "Station"), [], "a tapped creature")
        game, a = table(land(EVENDO), [Permanent(RELIC)])
        self.assertEqual(actions(game, a, "Station"), [], "an artifact that is not a creature")

    def test_only_as_a_sorcery(self):
        game, a = table(land(EVENDO), [Permanent(BEAR)], step="combat")
        self.assertEqual(actions(game, a, "Station"), [])
        game, a = table(land(EVENDO), [Permanent(BEAR)])
        game.active = 1
        self.assertEqual(actions(game, a, "Station"), [], "not on an opponent's turn")

    def test_the_land_need_not_be_untapped(self):
        permanent = land(EVENDO, tapped=True)
        game, a = table(permanent, [Permanent(BEAR)])
        activate(game, a, "Station")
        self.assertEqual(permanent.counters, {"charge": 2})

    def test_an_opponents_creature_cannot_be_tapped(self):
        game, a = table(land(EVENDO), [], theirs=[Permanent(BEAR)])
        self.assertEqual(actions(game, a, "Station"), [])


class ThresholdManaTests(unittest.TestCase):
    def cast_green(self, count, counters, creatures):
        spell = real("Green Many", "{G}" * count, "Instant", "Draw a card.", colors=("G",))
        t = Table(spell, n=0, mine=[land(EVENDO, counters), Permanent(FOREST)] + [Permanent(BEAR) for _ in range(creatures)])
        return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a)), t

    def test_evendo_makes_a_green_for_each_creature_with_twelve_counters(self):
        self.assertTrue(self.cast_green(3, 12, 3)[0])

    def test_but_not_with_eleven(self):
        ok, _ = self.cast_green(3, 11, 3)
        self.assertFalse(ok, "without the counters it makes just the one {G} its first ability does")

    def test_it_counts_the_creatures_you_control(self):
        self.assertTrue(self.cast_green(5, 12, 5)[0])
        self.assertFalse(self.cast_green(5, 12, 3)[0])

    def test_uthros_makes_a_blue_for_each_artifact_with_twelve_counters(self):
        spell = real("Blue Many", "{U}{U}{U}", "Instant", "Draw a card.", colors=("U",))
        for counters, expected in ((12, True), (11, False)):
            with self.subTest(counters=counters):
                t = Table(spell, n=0, mine=[land(UTHROS, counters), Permanent(ISLAND), Permanent(RELIC), Permanent(RELIC)])
                self.assertEqual(any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a)), expected)

    def test_the_first_ability_is_always_there(self):
        spell = real("Green", "{G}", "Instant", "Draw a card.", colors=("G",))
        t = Table(spell, n=0, mine=[land(EVENDO, 0)])
        self.assertTrue(any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a)))

    def test_paying_for_it_taps_the_land_and_the_payer(self):
        ok, t = self.cast_green(3, 12, 3)
        t.cast()
        self.assertTrue(t.a.battlefield[0].tapped and t.a.battlefield[1].tapped)


class AdagiaTests(unittest.TestCase):
    def table(self, counters, others=(), mana=4, step="main1"):
        game, a = table(land(ADAGIA, counters), [Permanent(c) for c in others] + lands(mana), step=step)
        return game, a

    def test_with_twelve_counters_it_copies_an_artifact_as_a_legendary_token(self):
        game, a = self.table(12, [RELIC])
        activate(game, a, "Create a token")
        tokens = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual(len(tokens), 1)
        self.assertIn("Legendary", tokens[0].card.type_line)
        self.assertIn("Artifact", tokens[0].card.type_line)
        self.assertEqual(tokens[0].card.name, "Relic")

    def test_an_enchantment_works_too(self):
        game, a = self.table(12, [SHRINE])
        activate(game, a, "Create a token")
        self.assertTrue(any(p.card.name == "Shrine" and p.card.type_line.startswith("Token") for p in a.battlefield))

    def test_the_original_is_not_changed(self):
        game, a = self.table(12, [RELIC])
        original = a.battlefield[1]
        activate(game, a, "Create a token")
        self.assertNotIn("Legendary", original.card.type_line)

    def test_not_with_eleven_counters(self):
        game, a = self.table(11, [RELIC])
        self.assertEqual(actions(game, a, "Create a token"), [])

    def test_it_needs_an_artifact_or_enchantment_of_yours_and_the_mana(self):
        game, a = self.table(12, [BEAR])
        self.assertEqual(actions(game, a, "Create a token"), [], "a creature is not an artifact")
        game, a = self.table(12, [RELIC], mana=3)
        self.assertEqual(actions(game, a, "Create a token"), [], "{3}{W} is four mana")

    def test_only_as_a_sorcery(self):
        game, a = self.table(12, [RELIC], step="combat")
        self.assertEqual(actions(game, a, "Create a token"), [])

    def test_it_taps_the_land_as_a_cost(self):
        game, a = self.table(12, [RELIC])
        activate(game, a, "Create a token")
        self.assertTrue(a.battlefield[0].tapped)


class KavaronTests(unittest.TestCase):
    def table(self, counters, others, lands_=(PLAINS, MOUNTAIN, MOUNTAIN)):
        game, a = table(land(KAVARON, counters), [Permanent(c) for c in others] + [Permanent(c) for c in lands_])
        return game, a

    def test_with_twelve_counters_it_sacrifices_a_land_for_a_robot_and_an_attack_bonus(self):
        game, a = self.table(12, [BEAR])
        activate(game, a, "Sacrifice a land")
        names = [p.card.name for p in a.battlefield]
        self.assertEqual(sum(n == "Robot" for n in names), 1)
        self.assertEqual(sum(c.type_line.endswith("Land") or "Land" in c.type_line for c in a.graveyard), 1, "a land was sacrificed")
        bear = next(p for p in a.battlefield if p.card.name == "Bear")
        self.assertEqual(game.power(bear), 3)
        self.assertTrue(game.has_keyword(bear, "haste"))

    def test_the_robot_is_a_two_two_artifact_creature_that_gets_the_bonus_too(self):
        game, a = self.table(12, [])
        activate(game, a, "Sacrifice a land")
        robot = next(p for p in a.battlefield if p.card.name == "Robot")
        self.assertIn("Artifact", robot.card.type_line)
        self.assertEqual((game.power(robot), game.toughness(robot)), (3, 2))

    def test_an_opponents_creatures_are_not_helped(self):
        game, a = self.table(12, [])
        game.seats[1].battlefield = [Permanent(BEAR)]
        activate(game, a, "Sacrifice a land")
        self.assertEqual(game.power(game.seats[1].battlefield[0]), 2)

    def test_not_with_eleven_counters(self):
        game, a = self.table(11, [BEAR])
        self.assertEqual(actions(game, a, "Sacrifice a land"), [])

    def test_it_needs_two_mana_and_a_land_to_sacrifice(self):
        game, a = self.table(12, [], lands_=(MOUNTAIN,))
        self.assertEqual(actions(game, a, "Sacrifice a land"), [], "one other land: {1}{R} needs two")


class SusurSecundiTests(unittest.TestCase):
    def table(self, counters, creatures, lands_=(SWAMP, SWAMP), step="main1", policy=None):
        game, a = table(land(SUSUR, counters), [Permanent(c) for c in creatures] + [Permanent(c) for c in lands_], step=step, policy=policy)
        a.library = [PLAINS] * 10
        return game, a

    def test_with_twelve_counters_it_draws_cards_equal_to_the_sacrificed_creatures_power(self):
        game, a = self.table(12, [BIG], )
        life = a.life
        activate(game, a, "Draw cards")
        self.assertEqual(len(a.hand), 7)
        self.assertEqual(a.life, life - 2)
        self.assertIn("Big", [c.name for c in a.graveyard])

    def test_you_choose_which_creature_to_sacrifice(self):
        for chosen, drawn in (("Small", 1), ("Big", 7)):
            with self.subTest(chosen=chosen):
                game, a = self.table(12, [SMALL, BIG], policy=pick(chosen))
                activate(game, a, "Draw cards")
                self.assertEqual(len(a.hand), drawn)
                self.assertIn(chosen, [c.name for c in a.graveyard])

    def test_not_with_eleven_counters(self):
        game, a = self.table(11, [BIG])
        self.assertEqual(actions(game, a, "Draw cards"), [])

    def test_it_needs_a_creature_and_two_mana(self):
        game, a = self.table(12, [])
        self.assertEqual(actions(game, a, "Draw cards"), [], "no creature to sacrifice")
        game, a = self.table(12, [BIG], lands_=(SWAMP,))
        self.assertEqual(actions(game, a, "Draw cards"), [], "{1}{B} is two mana")

    def test_only_as_a_sorcery(self):
        game, a = self.table(12, [BIG], step="combat")
        self.assertEqual(actions(game, a, "Draw cards"), [])


if __name__ == "__main__":
    unittest.main()
