"""Change the target of target spell (or ability) with a single target: Deflection, Divert, Imp's Mischief, Bolt Bend, Reroute."""

import unittest

from infernal_machine.effects import triggered_abilities
from infernal_machine.game import ACTIVATE, CAST, CHANGE_WHICH_PROMPT, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, CHANGE_TARGET_BOLT as BOLT, lands, OGRE, pick, real, Responder, run_stack, script, stack_fight, table3

SMITE = real("Smite", "{1}{W}", "Instant", "Destroy target creature an opponent controls.")
CLASH = real("Clash", "{1}{R}", "Instant", "Target creature you control fights target creature you don't control.")
DEFLECTION = real("Deflection", "{3}{U}", "Instant", "Change the target of target spell with a single target.")
DIVERT = real("Divert", "{U}{U}", "Instant", "Change the target of target spell with a single target unless that spell's controller pays {2}.")
MISCHIEF = real("Imp's Mischief", "{1}{R}", "Instant", "Change the target of target spell with a single target. You lose life equal to that spell's mana value.")
BEND = real("Bolt Bend", "{3}{R}", "Instant", "Change the target of target spell or ability with a single target.")
REROUTE = real("Reroute", "{R}", "Instant", "Change the target of target activated ability with a single target.")
PINGER = real("Pinger", "{1}", "Artifact", "{T}: Pinger deals 1 damage to any target.")


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DEFLECTION, DIVERT, MISCHIEF, BEND, REROUTE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class DeflectionTests(unittest.TestCase):
    def test_the_spell_hits_the_new_target(self):
        game, a, b, c, _ = stack_fight(BOLT, "Player: B", DEFLECTION, answers=("Spell", "Player: C"))
        self.assertEqual((a.life, b.life, c.life), (40, 40, 37))

    def test_without_the_response_it_hits_the_old_target(self):
        from tests.helpers import script
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
        from tests.helpers import script
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
        from tests.helpers import script
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
        from tests.helpers import script
        game, _ = table3(script("Player: B"))
        a, b, c = game.seats
        a.hand, a.battlefield = [BOLT], lands(2)
        b.hand, b.battlefield = [REROUTE], lands(3)
        game._perform(a, CAST + "Lightning Bolt")
        self.assertFalse(game._can_cast(b, REROUTE))

    def test_a_triggered_ability_is_a_target_for_bolt_bend_but_not_for_reroute(self):
        from tests.helpers import script
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


REBOUND = real("Rebound", "{1}{U}", "Instant", "Change the target of target spell that targets only a player. The new target must be a player.")
WYVERN = real("Silver Wyvern", "{2}{U}", "Creature — Drake", "Flying\n{U}: Change the target of target spell or ability that targets only this creature. "
              "The new target must be a creature.", "2", "2")
DRUBB = real("Muck Drubb", "{3}{B}", "Creature — Beast", "Flash\nWhen this creature enters, change the target of target spell that targets only a single "
             "creature to this creature.", "3", "3")
SPECIMEN = real("Hydroelectric Specimen", "{1}{U}", "Creature — Elemental", "Flash\nWhen this creature enters, you may change the target of target "
                "instant or sorcery spell with a single target to this creature.", "1", "2")
FLECTOMANCER = real("Goblin Flectomancer", "{R}", "Creature — Goblin", "Sacrifice this creature: You may change the targets of target instant "
                    "or sorcery spell.", "1", "1")
SPELLSKITE = real("Spellskite", "{0}", "Artifact Creature — Horror", "{U/P}: Change a target of target spell or ability to this creature.", "0", "4")
KILL = real("Smite", "{1}{W}", "Instant", "Destroy target creature an opponent controls.")


def respond(spell, aimed, on_battlefield, *answers, mine=(), theirs=(), act=None):
    """A casts `spell` at `aimed`; B (holding `on_battlefield` permanents) answers by `act(game, a, b)`; then the stack resolves."""
    from tests.helpers import script
    responder = Responder(*answers)
    game, _ = table3(script(*aimed), responder)
    a, b, c = game.seats
    a.hand, a.battlefield = [spell], lands(4) + [Permanent(x) for x in mine]
    b.battlefield = lands(5) + [Permanent(x, sick=False) for x in theirs]
    c.battlefield = [Permanent(BEAR)]
    game._perform(a, CAST + spell.name)
    act(game, a, b)
    while game.stack or game.pending:  # triggers go on the stack before the next thing resolves
        game._put_triggers_on_stack()
        if game.stack:
            game._resolve(game.stack.pop())
    game._check_state()
    return game, a, b, c, responder


def activate_on(game, seat, source_name):
    game._perform(seat, next(x for x in game.legal_actions(seat) if x.startswith(ACTIVATE) and source_name in x))


class OnlyOneThingTests(unittest.TestCase):
    def test_parse(self):
        for card in (REBOUND, WYVERN, DRUBB, SPECIMEN, FLECTOMANCER, SPELLSKITE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_rebound_aims_only_at_a_spell_that_targets_only_a_player(self):
        game, _ = table3(script("Bear"))
        a, b, c = game.seats
        a.hand, a.battlefield = [KILL], lands(3)
        b.hand, b.battlefield = [REBOUND], lands(4) + [Permanent(BEAR)]
        game._perform(a, CAST + "Smite")  # at a creature
        self.assertFalse(game._can_cast(b, REBOUND))

    def test_the_new_target_must_be_a_player(self):
        game, a, b, c, responder = respond(BOLT, ["Player: B"], REBOUND, "Spell", "Player: C", theirs=[BEAR],
                                           act=lambda g, a, b: (setattr(b, "hand", [REBOUND]), g._perform(b, CAST + "Rebound")))
        options = responder.asked[-1]
        self.assertTrue(options and all(label.startswith("Player") for label in options))  # not the Bear
        self.assertEqual((b.life, c.life), (40, 37))

    def test_silver_wyvern_redirects_a_spell_aimed_only_at_it_to_a_creature(self):
        game, a, b, c, responder = respond(BOLT, ["Silver Wyvern"], WYVERN, "Spell", "Bear", theirs=[WYVERN],
                                           act=lambda g, a, b: activate_on(g, b, "Silver Wyvern"))
        self.assertTrue(all(not label.startswith("Player") for label in responder.asked[-1]))
        self.assertEqual((b.life, c.life), (40, 40))
        self.assertEqual([p.card.name for p in c.battlefield], [])  # the Bolt killed C's Bear

    def test_silver_wyvern_cannot_aim_at_a_spell_aimed_at_something_else(self):
        game, _ = table3(script("Player: B"))
        a, b, c = game.seats
        a.hand, a.battlefield = [BOLT], lands(2)
        b.battlefield = lands(3) + [Permanent(WYVERN, sick=False)]
        game._perform(a, CAST + "Lightning Bolt")
        self.assertFalse([x for x in game.legal_actions(b) if x.startswith(ACTIVATE) and "Silver Wyvern" in x])

    def test_muck_drubb_takes_the_spell_aimed_at_a_single_creature(self):
        game, a, b, c, _ = respond(KILL, ["Bear"], DRUBB, "Spell", theirs=[BEAR],
                                   act=lambda g, a, b: (setattr(b, "hand", [DRUBB]), g._perform(b, CAST + "Muck Drubb")))
        self.assertEqual(sorted(p.card.name for p in b.battlefield if "Land" not in p.card.type_line), ["Bear"])  # the Drubb died instead
        self.assertEqual([x.name for x in b.graveyard], ["Muck Drubb"])

    def test_the_hydroelectric_specimen_may_decline(self):
        game, a, b, c, _ = respond(KILL, ["Bear"], SPECIMEN, "Spell", "No", theirs=[BEAR],
                                   act=lambda g, a, b: (setattr(b, "hand", [SPECIMEN]), g._perform(b, CAST + "Hydroelectric Specimen")))
        self.assertEqual(sorted(p.card.name for p in b.battlefield if "Land" not in p.card.type_line), ["Hydroelectric Specimen"])

    def test_the_hydroelectric_specimen_takes_the_spell_when_it_says_yes(self):
        game, a, b, c, _ = respond(KILL, ["Bear"], SPECIMEN, "Spell", "Yes", theirs=[BEAR],
                                   act=lambda g, a, b: (setattr(b, "hand", [SPECIMEN]), g._perform(b, CAST + "Hydroelectric Specimen")))
        self.assertEqual(sorted(p.card.name for p in b.battlefield if "Land" not in p.card.type_line), ["Bear"])

    def test_only_an_instant_or_sorcery_spell_is_a_target_of_the_specimen(self):
        from tests.helpers import script
        aura = real("Dampen", "{1}{U}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets -1/-0.")
        game, _ = table3(script("Bear"))
        a, b, c = game.seats
        a.hand, a.battlefield = [aura], lands(3)
        b.battlefield = [Permanent(BEAR)]
        game._perform(a, CAST + "Dampen")
        self.assertEqual(game.target_options("instant or sorcery spell with a single target", b), [])
        self.assertEqual(len(game.target_options("spell with a single target", b)), 1)

    def test_goblin_flectomancer_changes_the_targets_of_an_instant_or_sorcery(self):
        game, a, b, c, _ = respond(BOLT, ["Player: B"], FLECTOMANCER, "Spell", "Player: C", theirs=[FLECTOMANCER],
                                   act=lambda g, a, b: activate_on(g, b, "Goblin Flectomancer"))
        self.assertEqual((b.life, c.life), (40, 37))

    def test_spellskite_changes_a_target_to_itself(self):
        game, a, b, c, _ = respond(KILL, ["Bear"], SPELLSKITE, "Spell", theirs=[BEAR, SPELLSKITE],
                                   act=lambda g, a, b: activate_on(g, b, "Spellskite"))
        self.assertEqual(sorted(p.card.name for p in b.battlefield if "Land" not in p.card.type_line), ["Bear"])  # the Skite died

    def test_spellskite_picks_which_of_two_targets_to_change(self):
        shrink = real("Twin Shrink", "{2}{B}", "Instant", "Target creature gets -2/-2 until end of turn. Target creature gets -1/-1 until end of turn.")
        game, a, b, c, responder = respond(shrink, ["Ogre", "Bear"], SPELLSKITE, "Spell", "Bear", theirs=[BEAR, SPELLSKITE], mine=[OGRE],
                                           act=lambda g, a, b: activate_on(g, b, "Spellskite"))
        which = next(opts for opts in responder.asked if len(opts) == 2)  # the two targets it could change
        self.assertEqual(sorted(label.split(" ")[0] for label in which), ["Bear", "Ogre"])
        power = {p.card.name: (game.power(p), game.toughness(p)) for p in a.battlefield + b.battlefield if "Creature" in p.card.type_line}
        self.assertEqual(power["Spellskite"], (-1, 3))  # the second target became Spellskite: its 0/4 got -1/-1
        self.assertEqual(power["Ogre"], (1, 1))


if __name__ == "__main__":
    unittest.main()
