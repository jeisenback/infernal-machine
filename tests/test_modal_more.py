import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Modal, TapAll, activated_abilities, entwine_cost, escalate_cost, spell_effects,
                                      triggered_abilities)
from infernal_machine.game import ACTIVATE, CAST, DONE_MODES, ENTWINE_PROMPT, MODE_PROMPT, PASS, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

CRYPTIC = Card(name="Cryptic Command", mana_cost="{1}{U}{U}{U}", type_line="Instant",
               oracle_text="Choose two —\n• Counter target spell.\n• Return target permanent to its owner's hand.\n"
                           "• Tap all creatures your opponents control.\n• Draw a card.")
SWEEP = Card(name="Sweep", mana_cost="{1}{B}", type_line="Sorcery",
             oracle_text="Choose one —\n• You gain 4 life.\n• Draw a card.\nEntwine {2}")
STEP_UP = Card(name="Step Up", mana_cost="{U}", type_line="Sorcery",
               oracle_text="Escalate {1}\nChoose one or more —\n• You gain 2 life.\n• Draw a card.\n"
                           "• Each opponent loses 1 life.")
PRINCE = Card(name="Charming Prince", mana_cost="{2}{W}", type_line="Creature — Human Cleric", power="2", toughness="2",
              oracle_text="When Charming Prince enters, choose one —\n• You gain 3 life.\n• Draw a card.")
HUNTER = Card(name="Cunning Hunter", mana_cost="{2}", type_line="Creature — Elf", power="1", toughness="1",
              oracle_text="When Cunning Hunter enters, choose one —\n• Destroy target artifact.\n"
                          "• Destroy target enchantment.")
WELL = Card(name="Wishing Well", mana_cost="{2}", type_line="Artifact",
            oracle_text="{T}: Choose one —\n• You gain 2 life.\n• Draw a card.")
BREAKER = Card(name="Breaker", mana_cost="{2}", type_line="Artifact",
               oracle_text="{T}: Choose one —\n• Destroy target creature.\n• Destroy target enchantment.")
BADMODE = Card(name="Odd Prince", mana_cost="{2}", type_line="Creature — Human", power="1", toughness="1",
               oracle_text="When Odd Prince enters, choose one —\n• You gain 3 life.\n• Do something nobody understands.")


def modes(*picks):
    """Cast the first castable spell; answer mode prompts with the given option texts (or indexes) in order and
    entwine with `yes`."""
    wanted = iter(picks)
    base = pick(CAST)

    def policy(prompt, options):
        if prompt.startswith(MODE_PROMPT):
            want = next(wanted, 0)
            return options.index(want) if isinstance(want, str) else want
        return base(prompt, options)
    return policy


class ParseTests(unittest.TestCase):
    def test_tap_all(self):
        self.assertIsInstance(spell_effects(CRYPTIC)[0], Modal)
        self.assertIn(TapAll(), spell_effects(CRYPTIC)[0].modes[2])
        self.assertEqual(unsupported_lines(CRYPTIC), [])

    def test_entwine_and_escalate_costs(self):
        self.assertEqual((entwine_cost(SWEEP), escalate_cost(SWEEP)), ("{2}", None))
        self.assertEqual((entwine_cost(STEP_UP), escalate_cost(STEP_UP)), (None, "{1}"))
        self.assertEqual(unsupported_lines(SWEEP) + unsupported_lines(STEP_UP), [])

    def test_a_non_mana_escalate_cost_is_not_understood(self):
        card = Card(name="Brutality", mana_cost="{B}", type_line="Sorcery",
                    oracle_text="Escalate—Discard a card.\nChoose one or more —\n• You gain 2 life.\n• Draw a card.")
        self.assertEqual(unsupported_lines(card), ["Escalate—Discard a card."])

    def test_modal_triggers_and_abilities(self):
        [enters] = triggered_abilities(PRINCE)
        self.assertEqual((enters.event, len(enters.effects[0].modes)), ("enters", 2))
        [tap] = activated_abilities(WELL)
        self.assertTrue(tap.tap and isinstance(tap.effects[0], Modal))
        for card in (PRINCE, HUNTER, WELL, BREAKER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_one_unsupported_mode_spoils_the_ability_and_is_reported(self):
        self.assertEqual(triggered_abilities(BADMODE), ())
        self.assertEqual(len(unsupported_lines(BADMODE)), 1)


class EntwineTests(unittest.TestCase):
    def cast(self, mana, answer):
        policy = lambda prompt, options: (answer if prompt.startswith(ENTWINE_PROMPT) else modes(0)(prompt, options))
        game, players = table3(policy)
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [SWEEP], lands(mana), [BEAR] * 3
        game._priority_round(a)
        return game, a, players

    def test_entwining_does_both_and_pays_for_it(self):
        game, a, _ = self.cast(4, 0)
        self.assertEqual((a.life, len(a.hand), sum(p.tapped for p in a.battlefield)), (44, 1, 4))

    def test_declining_picks_one_mode_for_the_normal_cost(self):
        game, a, _ = self.cast(4, 1)
        self.assertEqual((a.life, len(a.hand), sum(p.tapped for p in a.battlefield)), (44, 0, 2))

    def test_not_offered_when_it_cannot_be_paid(self):
        game, a, players = self.cast(3, 0)
        self.assertFalse([p for p, _ in players[0].prompts if p.startswith(ENTWINE_PROMPT)])
        self.assertEqual((a.life, len(a.hand), sum(p.tapped for p in a.battlefield)), (44, 0, 2))


class EscalateTests(unittest.TestCase):
    def cast(self, mana, *picks):
        game, players = table3(modes(*picks))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [STEP_UP], lands(mana), [BEAR] * 3
        game._priority_round(a)
        return game, a, players

    def test_each_extra_mode_costs_the_escalate_cost(self):
        game, a, _ = self.cast(3, 0, 0, 0)  # gain 2, then draw, then each opponent loses 1: {U} + {1} + {1}
        self.assertEqual((a.life, len(a.hand), game.seats[1].life, sum(p.tapped for p in a.battlefield)), (42, 1, 39, 3))

    def test_a_single_mode_costs_the_normal_cost(self):
        game, a, _ = self.cast(3, 0, DONE_MODES)
        self.assertEqual((a.life, sum(p.tapped for p in a.battlefield)), (42, 1))

    def test_modes_that_cannot_be_afforded_are_not_offered(self):
        game, a, players = self.cast(2, 0, 0, 0)
        prompts = [o for p, o in players[0].prompts if p.startswith(MODE_PROMPT)]
        self.assertEqual(len(prompts), 2)  # after two modes ({U} + {1}) a third would cost one more than it has
        self.assertEqual(sum(p.tapped for p in a.battlefield), 2)


class ModalTriggerTests(unittest.TestCase):
    def test_the_controller_chooses_a_mode_when_it_enters(self):
        game, players = table3(modes(1))
        a = game.seats[0]
        a.library = [BEAR] * 3
        game._enter(a, Permanent(PRINCE))
        run_stack(game)
        self.assertEqual((a.life, len(a.hand)), (40, 1))  # the second mode: draw a card
        self.assertEqual(next(o for p, o in players[0].prompts if p.startswith(MODE_PROMPT)),
                         ["You gain 3 life.", "Draw a card."])

    def test_modes_without_targets_are_not_offered_and_no_mode_means_no_trigger(self):
        game, players = table3(modes(0))
        a = game.seats[0]
        game._enter(a, Permanent(HUNTER))
        game._put_triggers_on_stack()
        self.assertEqual(game.stack, [])
        self.assertFalse([p for p, _ in players[0].prompts if p.startswith(MODE_PROMPT)])

    def test_only_modes_with_targets_are_offered(self):
        game, players = table3(modes(0))
        a = game.seats[0]
        game.seats[1].battlefield = [Permanent(Card(name="Relic", type_line="Artifact"))]
        game._enter(a, Permanent(HUNTER))
        run_stack(game)
        self.assertEqual(next(o for p, o in players[0].prompts if p.startswith(MODE_PROMPT)), ["Destroy target artifact."])
        self.assertEqual(game.seats[1].battlefield, [])


class ModalAbilityTests(unittest.TestCase):
    def activate(self, card, *picks, opponents=()):
        game, players = table3(lambda prompt, options: (modes(*picks)(prompt, options) if prompt.startswith(MODE_PROMPT)
                                                       else next((i for i, o in enumerate(options) if o.startswith(ACTIVATE)),
                                                                 options.index(PASS) if PASS in options else 0)))
        a = game.seats[0]
        well = Permanent(card)
        a.battlefield, a.library = [well], [BEAR] * 3
        game.seats[1].battlefield = list(opponents)
        game._priority_round(a)
        return game, a, well, players

    def test_activating_chooses_a_mode(self):
        game, a, well, _ = self.activate(WELL, 1)
        self.assertEqual((well.tapped, a.life, len(a.hand)), (True, 40, 1))

    def test_it_cannot_be_activated_when_no_mode_has_a_target(self):
        game, a, well, players = self.activate(BREAKER, 0)
        self.assertEqual((well.tapped, [p for p, _ in players[0].prompts if p.startswith(MODE_PROMPT)]), (False, []))

    def test_it_can_when_one_does(self):
        game, a, well, _ = self.activate(BREAKER, 0, opponents=[Permanent(BEAR)])
        self.assertEqual((well.tapped, game.seats[1].battlefield), (True, []))


class TapAllTests(unittest.TestCase):
    def test_taps_only_opponents_creatures(self):
        game, _ = table3()
        a, b, c = game.seats
        mine, theirs, other = Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)
        land = Permanent(Card(name="Forest", type_line="Basic Land"))
        a.battlefield, b.battlefield, c.battlefield = [mine], [theirs, land], [other]
        TapAll().resolve(game, a, None)
        self.assertEqual((mine.tapped, theirs.tapped, other.tapped, land.tapped), (False, True, True, False))
