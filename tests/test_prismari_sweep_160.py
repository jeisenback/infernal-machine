"""The eight Prismari creatures, enchantment and counterspell of the precon decks that no test named (issue #160), each played from
its real Oracle text, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, BIRD, OGRE, attack_all
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, battlefield_names, real
from tests.test_triggers_80 import FOREST, PLAINS, RELIC, SHRINE
from tests.test_x_targets import script

SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")
BOLT = real("Bolt", "{1}{R}", "Instant", "Bolt deals 3 damage to target creature.", colors=("R",))
SORCERY = real("Plain Sorcery", "{1}", "Sorcery", "You gain 1 life.")
CREATURE_SPELL = real("Plain Creature", "{1}", "Creature — Test", "", "1", "1")
CANTRIP = real("Cantrip", "{1}", "Instant", "You gain 1 life.")


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def fight(game, seat):
    game.active = seat.index
    game.combat.declare_attackers(seat)
    run_stack(game)
    game.combat.declare_blockers()
    run_stack(game)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)


def step(game, seat, name):
    game.active = seat.index
    game.step = name
    game._turn_based_actions(seat)
    run_stack(game)


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


MASTERMIND = real("Faerie Mastermind", "{1}{U}", "Creature — Faerie Rogue",
                  "Flash\nFlying\nWhenever an opponent draws their second card each turn, you draw a card.\n{3}{U}: Each player draws a card.",
                  "2", "1")


class FaerieMastermindTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        a.battlefield = [Permanent(MASTERMIND)]
        for seat in game.seats:
            seat.library = [FOREST] * 10
        return game, a, b, c

    def test_parse(self):
        self.assertEqual(unsupported_lines(MASTERMIND), [])

    def test_the_second_card_an_opponent_draws_in_a_turn_draws_you_one(self):
        game, a, b, c = self.table()
        game.draw(b, 1)
        run_stack(game)
        self.assertEqual(len(a.hand), 0)
        game.draw(b, 1)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_only_the_second_card_and_once_per_opponent(self):
        game, a, b, c = self.table()
        game.draw(b, 3)
        game.draw(c, 2)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)  # one for each opponent's second card; the third card did nothing

    def test_your_own_second_card_does_nothing(self):
        game, a, b, c = self.table()
        game.draw(a, 2)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)

    def test_its_ability_makes_each_player_draw_a_card(self):
        game, a, b, c = self.table()
        a.battlefield += lands(4)
        activate(game, a, "Each player draws a card")
        self.assertEqual([len(s.hand) for s in game.seats], [1, 1, 1])

    def test_the_ability_needs_four_mana(self):
        game, a, b, c = self.table()
        a.battlefield += lands(3)
        self.assertFalse(any(x.startswith(ACTIVATE) and "Each player" in x for x in game.legal_actions(a)))

    def test_flash_lets_it_be_cast_at_instant_speed(self):
        t = Table(MASTERMIND, n=2)
        t.game.step = "end"
        self.assertIn(CAST + "Faerie Mastermind", t.game.legal_actions(t.a))


ITERATION = real("Determined Iteration", "{1}{R}", "Enchantment",
                 "At the beginning of combat on your turn, populate. The token created this way gains haste. Sacrifice it at the beginning of "
                 "the next end step. (To populate, create a token that's a copy of a creature token you control.)")


class DeterminedIterationTests(unittest.TestCase):
    def table(self, tokens=1):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(ITERATION)] + [Permanent(SPIRIT, sick=True) for _ in range(tokens)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(ITERATION), [])

    def test_at_the_beginning_of_combat_it_copies_a_token_with_haste(self):
        game, a, b = self.table()
        step(game, a, "beginning_of_combat")
        spirits = [p for p in a.battlefield if p.card.name == "Spirit"]
        self.assertEqual(len(spirits), 2)
        self.assertEqual(sorted(game.has_keyword(p, "haste") for p in spirits), [False, True])  # only the new copy

    def test_the_copy_is_sacrificed_at_the_next_end_step_and_the_original_stays(self):
        game, a, b = self.table()
        step(game, a, "beginning_of_combat")
        step(game, a, "end")
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Spirit"]), 1)

    def test_nothing_to_copy_without_a_creature_token(self):
        game, a, b = self.table(tokens=0)
        a.battlefield.append(Permanent(BEAR))
        step(game, a, "beginning_of_combat")
        self.assertEqual(battlefield_names(a), ["Bear", "Determined Iteration"])

    def test_only_on_your_own_turn(self):
        game, a, b = self.table()
        step(game, b, "beginning_of_combat")
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Spirit"]), 1)

    def test_it_copies_only_a_creature_token_you_control(self):
        game, a, b = self.table(tokens=0)
        b.battlefield = [Permanent(SPIRIT)]
        step(game, a, "beginning_of_combat")
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Spirit"]), 0)


EMERITUS = real("Archmage Emeritus", "{2}{U}{U}", "Creature — Human Wizard", "Magecraft — Whenever you cast or copy an instant or sorcery spell, draw a card.",
                "2", "2")


class ArchmageEmeritusTests(unittest.TestCase):
    def cast(self, spell, *answers):
        t = Table(spell, *answers, mine=[Permanent(EMERITUS)])
        t.a.library = [FOREST] * 5
        return t.cast()

    def test_parse(self):
        self.assertEqual(unsupported_lines(EMERITUS), [])

    def test_casting_an_instant_or_a_sorcery_draws_a_card(self):
        self.assertEqual(len(self.cast(CANTRIP).a.hand), 1)
        self.assertEqual(len(self.cast(SORCERY).a.hand), 1)

    def test_a_creature_or_other_spell_does_not(self):
        self.assertEqual(len(self.cast(CREATURE_SPELL).a.hand), 0)
        self.assertEqual(len(self.cast(SHRINE).a.hand), 0)

    def test_copying_one_draws_a_card_too(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(EMERITUS)]
        a.library = [FOREST] * 5
        game._observe("copy", CANTRIP, a)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_an_opponents_spell_does_not(self):
        t = Table(CANTRIP, mine=[Permanent(EMERITUS)])
        t.b.hand, t.b.battlefield = [CANTRIP], lands(2)
        t.a.hand = []
        t.a.library = [FOREST] * 5
        t.game.active = 1
        t.game._perform(t.b, CAST + "Cantrip")
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)


BORROWER = real("Brazen Borrower", "{1}{U}{U}", "Creature — Faerie Rogue", "Flash\nFlying\nThis creature can block only creatures with flying.", "3", "1")


class BrazenBorrowerTests(unittest.TestCase):
    def blocked_by(self, attacker):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(attacker, sick=False)]
        b.battlefield = [Permanent(BORROWER, sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        return bool(game.combat.attacks[0].blockers)

    def test_parse(self):
        self.assertEqual(unsupported_lines(BORROWER), [])

    def test_it_can_block_a_flyer_but_not_a_ground_creature(self):
        self.assertTrue(self.blocked_by(BIRD))
        self.assertFalse(self.blocked_by(BEAR))

    def test_it_can_still_attack_normally_and_has_flying(self):
        game, _ = table3(pick())
        self.assertTrue(game.has_keyword(Permanent(BORROWER), "flying"))

    def test_flash(self):
        t = Table(BORROWER, n=3)
        t.game.step = "end"
        self.assertIn(CAST + "Brazen Borrower", t.game.legal_actions(t.a))


CRAFTER = real("Curiosity Crafter", "{3}{U}", "Creature — Bird Wizard",
               "Flying\nYou have no maximum hand size.\nWhenever a creature token you control deals combat damage to a player, draw a card.", "3", "3")


class CuriosityCrafterTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(CRAFTER), [])

    def cleanup(self, crafter):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(CRAFTER)] if crafter else []
        a.hand = [FOREST] * 9
        end_turn(game, a)
        return a

    def test_no_maximum_hand_size(self):
        self.assertEqual(len(self.cleanup(True).hand), 9)

    def test_without_it_you_discard_down_to_seven(self):
        a = self.cleanup(False)
        self.assertEqual((len(a.hand), len(a.graveyard)), (7, 2))

    def attack(self, attackers):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(CRAFTER, sick=True)] + [Permanent(c, sick=False) for c in attackers]
        a.library = [FOREST] * 5
        fight(game, a)
        return a

    def test_each_creature_token_that_hits_a_player_draws_a_card(self):
        a = self.attack([SPIRIT, SPIRIT])
        self.assertEqual(len(a.hand), 2)

    def test_a_nontoken_creature_does_not(self):
        a = self.attack([BEAR])
        self.assertEqual(len(a.hand), 0)

    def test_a_blocked_token_does_not(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(CRAFTER, sick=True), Permanent(SPIRIT, sick=False)]
        b.battlefield = [Permanent(OGRE, sick=False)]
        a.library = [FOREST] * 5
        fight(game, a)
        self.assertEqual(len(a.hand), 0)


STORMSINGER = real("Redoubled Stormsinger", "{2}{R}", "Creature — Orc Wizard",
                   "First strike\nWhenever this creature attacks, for each creature token you control that entered this turn, create a tapped and "
                   "attacking token that's a copy of that token. At the beginning of the next end step, sacrifice those tokens.", "3", "3")


class RedoubledStormsingerTests(unittest.TestCase):
    def attack(self, entered_this_turn=True, nontoken=False):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        singer = Permanent(STORMSINGER, sick=False)
        token = Permanent(SPIRIT, sick=True, entered_turn=game.turn if entered_this_turn else game.turn - 1)
        a.battlefield = [singer, token] + ([Permanent(BEAR, sick=True, entered_turn=game.turn)] if nontoken else [])
        game.active = 0
        game.combat.declare_attackers(a)
        run_stack(game)
        return game, a, singer

    def test_parse(self):
        self.assertEqual(unsupported_lines(STORMSINGER), [])

    def test_it_makes_a_tapped_attacking_copy_of_a_token_that_entered_this_turn(self):
        game, a, singer = self.attack()
        copies = [p for p in a.battlefield if p.card.name == "Spirit"]
        self.assertEqual(len(copies), 2)
        attacking = [att.attacker for att in game.combat.attacks]
        new = [p for p in copies if p in attacking]
        self.assertEqual(len(new), 1)
        self.assertTrue(new[0].tapped)

    def test_a_token_from_an_earlier_turn_is_not_copied(self):
        game, a, singer = self.attack(entered_this_turn=False)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Spirit"]), 1)

    def test_a_nontoken_creature_is_not_copied(self):
        game, a, singer = self.attack(nontoken=True)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Bear"]), 1)

    def test_the_copies_are_sacrificed_at_the_next_end_step(self):
        game, a, singer = self.attack()
        step(game, a, "end")
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Spirit"]), 1)

    def test_it_has_first_strike(self):
        game, _ = table3(pick())
        self.assertTrue(game.has_keyword(Permanent(STORMSINGER), "first strike"))


DENIAL = real("Arcane Denial", "{1}{U}", "Instant", "Counter target spell. Its controller may draw up to two cards at the beginning of the next turn's "
                                                    "upkeep.\nYou draw a card at the beginning of the next turn's upkeep.")


class ArcaneDenialTests(unittest.TestCase):
    def setup(self, *b_answers):
        game, _ = table3(script("Gain"))
        a, b, _ = game.seats
        a.hand = [DENIAL]
        a.battlefield = lands(2)
        a.library = [FOREST] * 5
        gain = real("Gain", "{1}", "Instant", "You gain 5 life.")
        b.hand, b.battlefield = [gain], lands(2)
        b.library = [FOREST] * 5
        b.player.policy = script(*b_answers)
        game.active = 1
        game._perform(b, CAST + "Gain")
        game._perform(a, CAST + "Arcane Denial")
        run_stack(game)
        return game, a, b

    def upkeep(self, game):
        game.turn += 1
        game.step = "upkeep"
        game._turn_based_actions(game.seats[0])
        run_stack(game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(DENIAL), [])

    def test_the_spell_is_countered(self):
        game, a, b = self.setup("2")
        self.assertEqual(b.life, 40)
        self.assertEqual(sorted(c.name for c in b.graveyard), ["Gain"])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Arcane Denial"])

    def test_nothing_is_drawn_until_the_next_upkeep(self):
        game, a, b = self.setup("2")
        self.assertEqual((len(a.hand), len(b.hand)), (0, 0))

    def test_at_the_next_upkeep_you_draw_one_and_the_controller_may_draw_up_to_two(self):
        game, a, b = self.setup("2")
        self.upkeep(game)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 2))

    def test_the_controller_may_draw_fewer(self):
        game, a, b = self.setup("1")
        self.upkeep(game)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 1))
        game2, a2, b2 = self.setup("0")
        self.upkeep(game2)
        self.assertEqual((len(a2.hand), len(b2.hand)), (1, 0))

    def test_it_happens_only_once(self):
        game, a, b = self.setup("2")
        self.upkeep(game)
        self.upkeep(game)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 2))


MENTOR = real("Stormcatch Mentor", "{U}{R}", "Creature — Otter Wizard",
              "Haste\nProwess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)\nInstant and sorcery spells you "
              "cast cost {1} less to cast.", "1", "1")


class StormcatchMentorTests(unittest.TestCase):
    def castable(self, spell, n, mentor=True):
        t = Table(spell, n=n, mine=[Permanent(MENTOR)] if mentor else [Permanent(BEAR)])
        return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a))

    def test_parse(self):
        self.assertEqual(unsupported_lines(MENTOR), [])

    def test_instants_and_sorceries_cost_exactly_one_less(self):
        two_instant = real("Two Instant", "{2}", "Instant", "You gain 1 life.")
        two_sorcery = real("Two Sorcery", "{2}", "Sorcery", "You gain 1 life.")
        for spell in (two_instant, two_sorcery):
            self.assertTrue(self.castable(spell, 1), spell.name)
            self.assertFalse(self.castable(spell, 0), spell.name)
            self.assertFalse(self.castable(spell, 1, mentor=False), spell.name)

    def test_creature_and_other_spells_cost_full_price(self):
        self.assertFalse(self.castable(real("Two Creature", "{2}", "Creature — Test", "", "1", "1"), 1))
        self.assertFalse(self.castable(real("Two Artifact", "{2}", "Artifact", ""), 1))

    def test_prowess_a_noncreature_spell_gives_plus_one_plus_one_until_end_of_turn(self):
        mentor = Permanent(MENTOR)
        t = Table(CANTRIP, mine=[mentor]).cast()
        self.assertEqual((t.game.power(mentor), t.game.toughness(mentor)), (2, 2))
        end_turn(t.game, t.a)
        self.assertEqual(t.game.power(mentor), 1)

    def test_a_creature_spell_gives_no_prowess(self):
        mentor = Permanent(MENTOR)
        t = Table(CREATURE_SPELL, mine=[mentor]).cast()
        self.assertEqual(t.game.power(mentor), 1)

    def test_it_has_haste(self):
        game, _ = table3(pick())
        self.assertTrue(game.has_keyword(Permanent(MENTOR), "haste"))
