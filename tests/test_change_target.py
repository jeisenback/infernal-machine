"""Change the target of target spell (or ability) with a single target: Deflection, Divert, Imp's Mischief, Bolt Bend, Reroute."""

import unittest

from infernal_machine.effects import triggered_abilities
from infernal_machine.game import ACTIVATE, CAST, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import pick

BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")
SMITE = real("Smite", "{1}{W}", "Instant", "Destroy target creature an opponent controls.")
CLASH = real("Clash", "{1}{R}", "Instant", "Target creature you control fights target creature you don't control.")
DEFLECTION = real("Deflection", "{3}{U}", "Instant", "Change the target of target spell with a single target.")
DIVERT = real("Divert", "{U}{U}", "Instant", "Change the target of target spell with a single target unless that spell's controller pays {2}.")
MISCHIEF = real("Imp's Mischief", "{1}{R}", "Instant", "Change the target of target spell with a single target. You lose life equal to that spell's mana value.")
BEND = real("Bolt Bend", "{3}{R}", "Instant", "Change the target of target spell or ability with a single target.")
REROUTE = real("Reroute", "{R}", "Instant", "Change the target of target activated ability with a single target.")
PINGER = real("Pinger", "{1}", "Artifact", "{T}: Pinger deals 1 damage to any target.")


class Responder:
    """Seat B's replies, remembering what it was asked for a target."""

    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, prompt, options):
        if prompt.startswith(TARGET_PROMPT):
            self.asked.append(list(options))
        return pick(self.answers.pop(0) if self.answers else "Pass")(prompt, options)


def stack_fight(spell, aimed, response, *, mine=(), theirs=(), third=(), answers=(), a_answers=(), counter=None, n=6, b_lands=6):
    """A casts `spell` at `aimed`; B (with `response`) answers it with the retargeting spell, and the stack resolves."""
    from tests.test_x_targets import script
    responder = counter or Responder(*answers)
    game, _ = table3(script(aimed, *a_answers), responder)
    a, b, c = game.seats
    a.hand, a.battlefield = [spell], lands(n)
    a.battlefield += [Permanent(x) for x in mine]
    b.hand, b.battlefield = [response], lands(b_lands) + [Permanent(x) for x in theirs]
    c.battlefield = [Permanent(x) for x in third]
    game._perform(a, CAST + spell.name)
    game._perform(b, CAST + response.name)
    run_stack(game)
    game._check_state()
    return game, a, b, c, responder


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DEFLECTION, DIVERT, MISCHIEF, BEND, REROUTE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class DeflectionTests(unittest.TestCase):
    def test_the_spell_hits_the_new_target(self):
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", DEFLECTION, answers=("Spell", "Player: C"))
        self.assertEqual((a.life, b.life, c.life), (40, 40, 37))

    def test_without_the_response_it_hits_the_old_target(self):
        from tests.test_x_targets import script
        game, _ = table3(script("Player: B"))
        a, b, c = game.seats
        a.hand, a.battlefield = [BOLT], lands(2)
        game._perform(a, CAST + "Lightning Bolt")
        run_stack(game)
        self.assertEqual((b.life, c.life), (37, 40))

    def test_the_old_target_is_not_offered_but_every_other_legal_one_is(self):
        game, a, b, c, responder = stack_fight(BOLT, "Player: B", DEFLECTION, theirs=(BEAR,), answers=("Spell", "Player: C"))
        new_choice = responder.asked[-1]
        self.assertFalse(any(label.startswith("Player: B") for label in new_choice))
        self.assertTrue(any(label.startswith("Player: A") for label in new_choice))  # the spell's own controller counts
        self.assertTrue(any(label.startswith("Bear") for label in new_choice))

    def test_the_new_target_is_chosen_from_the_spells_point_of_view(self):
        """"creature an opponent controls" means an opponent of the spell's controller, not of the player who redirects it."""
        game, a, b, c, responder = stack_fight(SMITE, "Bear", DEFLECTION, mine=(OGRE,), theirs=(BEAR,), third=(OGRE,),
                                               answers=("Spell", "Ogre"))
        labels = responder.asked[-1]
        self.assertEqual(len(labels), 1)  # only C's Ogre: not A's own Ogre, not B's Bear it already had
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], ["Ogre"])
        self.assertEqual([p.card.name for p in b.battlefield if "Land" not in p.card.type_line], ["Bear"])
        self.assertEqual(c.battlefield, [])

    def test_with_no_other_legal_target_nothing_changes(self):
        game, a, b, c, _ = stack_fight(SMITE, "Bear", DEFLECTION, theirs=(BEAR,), answers=("Spell",))
        self.assertEqual([p.card.name for p in b.battlefield if "Land" not in p.card.type_line], [])

    def test_a_spell_with_two_targets_cannot_be_aimed_at(self):
        from tests.test_x_targets import script
        game, _ = table3(script("Ogre", "Bear"))
        a, b, c = game.seats
        a.hand, a.battlefield = [CLASH], lands(3) + [Permanent(OGRE)]
        b.hand, b.battlefield = [DEFLECTION], lands(6) + [Permanent(BEAR)]
        game._perform(a, CAST + "Clash")
        self.assertFalse(game._can_cast(b, DEFLECTION))

    def test_it_is_not_castable_with_nothing_on_the_stack_or_at_an_ability(self):
        game, _ = table3()
        b = game.seats[1]
        b.hand, b.battlefield = [DEFLECTION], lands(6)
        self.assertFalse(game._can_cast(b, DEFLECTION))


class VariantTests(unittest.TestCase):
    def test_divert_changes_it_unless_the_controller_pays(self):
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", DIVERT, answers=("Spell", "Player: C"), a_answers=("Pay",), n=6, b_lands=2)
        self.assertEqual((b.life, c.life), (37, 40))  # A paid {2}: the target stays
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", DIVERT, answers=("Spell", "Player: C"), a_answers=("Don't",), n=6, b_lands=2)
        self.assertEqual((b.life, c.life), (40, 37))

    def test_divert_changes_it_when_the_controller_cannot_pay(self):
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", DIVERT, answers=("Spell", "Player: C"), n=1, b_lands=2)
        self.assertEqual((b.life, c.life), (40, 37))

    def test_imps_mischief_costs_its_caster_life_equal_to_the_mana_value(self):
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", MISCHIEF, answers=("Spell", "Player: C"))
        self.assertEqual((a.life, b.life, c.life), (40, 39, 37))  # B lost the Bolt's mana value, 1

    def test_imps_mischief_can_send_the_spell_back_at_its_controller(self):
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", MISCHIEF, answers=("Spell", "Player: A"))
        self.assertEqual((a.life, b.life), (37, 39))


class AbilityTests(unittest.TestCase):
    def activated(self, response, *answers):
        from tests.test_x_targets import script
        responder = Responder(*answers)
        game, _ = table3(script("Player: B"), responder)
        a, b, c = game.seats
        a.battlefield = [Permanent(PINGER, sick=False)]
        b.hand, b.battlefield = [response], lands(6)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE)))
        return game, a, b, c, responder

    def test_bolt_bend_redirects_an_ability(self):
        game, a, b, c, _ = self.activated(BEND, "Ability", "Player: C")
        game._perform(b, CAST + "Bolt Bend")
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 39))

    def test_reroute_aims_only_at_activated_abilities(self):
        game, a, b, c, _ = self.activated(REROUTE, "Ability", "Player: C")
        game._perform(b, CAST + "Reroute")
        run_stack(game)
        self.assertEqual((b.life, c.life), (40, 39))

    def test_reroute_cannot_aim_at_a_spell_or_a_triggered_ability(self):
        from tests.test_x_targets import script
        game, _ = table3(script("Player: B"))
        a, b, c = game.seats
        a.hand, a.battlefield = [BOLT], lands(2)
        b.hand, b.battlefield = [REROUTE], lands(3)
        game._perform(a, CAST + "Lightning Bolt")
        self.assertFalse(game._can_cast(b, REROUTE))

    def test_a_triggered_ability_is_a_target_for_bolt_bend_but_not_for_reroute(self):
        from tests.test_x_targets import script
        game, _ = table3(script("Player: B"))
        a, b, c = game.seats
        prober = Permanent(real("Prober", "{1}", "Creature — Human", "When this creature enters, it deals 1 damage to any target.", "1", "1"))
        a.battlefield = [prober]
        game._queue(triggered_abilities(prober.card)[0], prober, a)
        game._put_triggers_on_stack()
        b.hand, b.battlefield = [BEND, REROUTE], lands(6)
        self.assertTrue(game._can_cast(b, BEND))
        self.assertFalse(game._can_cast(b, REROUTE))

    def test_a_spell_only_is_not_an_ability_target(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, c = game.seats
        a.battlefield = [Permanent(PINGER, sick=False)]
        b.hand, b.battlefield = [DEFLECTION], lands(6)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE)))
        self.assertFalse(game._can_cast(b, DEFLECTION))  # Deflection says "spell"


if __name__ == "__main__":
    unittest.main()
