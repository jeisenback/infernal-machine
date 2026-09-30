import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Exile, ExileUntilLeaves, Modal, TargetDraw, TargetGainLife, TargetLoseLife,
                                      spell_effects, triggered_abilities)
from infernal_machine.game import CAST, DONE_MODES, MODE_PROMPT, PASS, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick, table
from tests.test_exile import COMMANDER, OGRE
from tests.test_mass_effects import table3
from tests.test_tokens import RAISE
from tests.test_triggers import MULLDRIFTER

OBLIVION_RING = Card(name="Oblivion Ring", mana_cost="{2}{W}", type_line="Enchantment",
                     oracle_text="When Oblivion Ring enters the battlefield, exile another target nonland permanent.\n"
                                 "When Oblivion Ring leaves the battlefield, return the exiled card to the battlefield "
                                 "under its owner's control.")
BANISHING_LIGHT = Card(name="Banishing Light", mana_cost="{2}{W}", type_line="Enchantment",
                       oracle_text="When Banishing Light enters the battlefield, exile target nonland permanent an "
                                   "opponent controls until Banishing Light leaves the battlefield.")
FIEND_HUNTER = Card(name="Fiend Hunter", mana_cost="{1}{W}{W}", type_line="Creature — Human Cleric", power="1", toughness="3",
                    oracle_text="When Fiend Hunter enters the battlefield, you may exile another target creature.\n"
                                "When Fiend Hunter leaves the battlefield, return the exiled card to the battlefield "
                                "under its owner's control.")
SMASH = Card(name="Smash", mana_cost="{R}", type_line="Instant", oracle_text="Destroy target artifact.")
RELIC = Card(name="Relic", type_line="Artifact")
CHOOSE_ONE = Card(name="Charm", mana_cost="{1}{U}", type_line="Instant",
                  oracle_text="Choose one —\n• Destroy target artifact.\n• Target player draws a card.\n• You gain 3 life.")
CHOOSE_TWO = Card(name="Command", mana_cost="{3}{R}", type_line="Sorcery",
                  oracle_text="Choose two —\n• Target opponent loses 3 life.\n• You gain 3 life.\n• Draw a card.")
BOTH = Card(name="Split", mana_cost="{2}", type_line="Sorcery",
            oracle_text="Choose one or both —\n• Destroy target artifact.\n• You gain 2 life.")


def cast_policy(*mode_picks):
    """Cast the first castable spell; answer mode prompts with the given picks (texts or indexes) in order."""
    picks = iter(mode_picks)
    base = pick(CAST)

    def policy(prompt, options):
        if prompt.startswith(MODE_PROMPT):
            want = next(picks, 0)
            return options.index(want) if isinstance(want, str) else want
        return base(prompt, options)
    return policy


class LinkedExileTests(unittest.TestCase):
    def test_parsing_both_wordings(self):
        [ring] = triggered_abilities(OBLIVION_RING)
        self.assertEqual(ring.effects, (ExileUntilLeaves("nonland permanent", another=True),))
        [light] = triggered_abilities(BANISHING_LIGHT)
        self.assertEqual(light.effects, (ExileUntilLeaves("nonland permanent an opponent controls"),))
        [hunter] = triggered_abilities(FIEND_HUNTER)
        self.assertTrue(hunter.optional)
        plain = Card(name="Exiler", oracle_text="When Exiler enters the battlefield, exile target creature.")
        self.assertEqual(triggered_abilities(plain)[0].effects, (Exile("creature"),))  # no return line: permanent

    def test_report(self):
        for card in (OBLIVION_RING, BANISHING_LIGHT, FIEND_HUNTER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_exile_and_return_when_the_source_leaves(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        seat = game.seats[0]
        seat.hand = [OBLIVION_RING]
        seat.battlefield = lands(3)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(seat)
        self.assertEqual((game.seats[1].battlefield, game.seats[1].exile), ([], [OGRE]))
        ring = seat.battlefield[-1]
        game.destroy(ring)
        self.assertEqual([p.card for p in game.seats[1].battlefield], [OGRE])  # back under its owner's control
        self.assertEqual(game.seats[1].exile, [])
        self.assertTrue(game.seats[1].battlefield[0].sick)  # a new object

    def test_returned_creature_triggers_again(self):
        game, _, _ = table(pick(CAST, "Mulldrifter"))
        seat = game.seats[0]
        seat.hand = [BANISHING_LIGHT]
        seat.battlefield = lands(3)
        game.seats[1].battlefield = [Permanent(MULLDRIFTER)]
        game._priority_round(seat)
        self.assertEqual(len(game.seats[1].hand), 0)
        game.destroy(seat.battlefield[-1])
        game._priority_round(seat)  # the returning Mulldrifter's trigger goes on the stack and resolves
        self.assertEqual(len(game.seats[1].hand), 2)

    def test_it_cannot_target_itself_with_another(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [OBLIVION_RING]
        seat.battlefield = lands(3)
        game._priority_round(seat)
        self.assertEqual(seat.battlefield[-1].card, OBLIVION_RING)  # nothing else to exile: stays, exiling nothing
        self.assertEqual(seat.exile, [])

    def test_tokens_are_gone_for_good(self):
        game, _, _ = table(pick(CAST, "Soldier"))
        seat = game.seats[0]
        seat.hand = [BANISHING_LIGHT]
        seat.battlefield = lands(3)
        game.create_tokens(game.seats[1], spell_effects(RAISE)[0].token, 1)
        game._priority_round(seat)
        game.destroy(seat.battlefield[-1])
        self.assertEqual((game.seats[1].battlefield, game.seats[1].exile), ([], []))

    def test_source_leaving_first_means_nothing_is_exiled(self):
        game, _, _ = table()
        ring = Permanent(OBLIVION_RING)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game.exile_until_leaves(game.seats[1].battlefield[0], ring)  # the ring isn't on the battlefield
        self.assertEqual(len(game.seats[1].battlefield), 1)

    def test_commander_may_go_to_the_command_zone_and_then_is_not_returned(self):
        game, _, b = table(pick(CAST, "Omnath"), pick("Command zone"))
        seat = game.seats[0]
        seat.hand = [BANISHING_LIGHT]
        seat.battlefield = lands(3)
        game.seats[1].commander_names = {"Omnath"}
        game.seats[1].battlefield = [Permanent(COMMANDER)]
        game._priority_round(seat)
        self.assertEqual(game.seats[1].command_zone, [COMMANDER])
        game.destroy(seat.battlefield[-1])
        self.assertEqual(game.seats[1].battlefield, [])  # it was never in exile, so nothing returns

    def test_fiend_hunter_is_optional_and_returns_on_death(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        seat = game.seats[0]
        seat.hand = [FIEND_HUNTER]
        seat.battlefield = lands(3)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(seat)
        self.assertEqual(game.seats[1].exile, [OGRE])
        game.destroy(seat.battlefield[-1])
        game._check_state()
        self.assertEqual([p.card for p in game.seats[1].battlefield], [OGRE])


class ModalTests(unittest.TestCase):
    def test_parsing(self):
        [modal] = spell_effects(CHOOSE_ONE)
        self.assertEqual((modal.min, modal.max, len(modal.modes)), (1, 1, 3))
        self.assertEqual(modal.modes[1], (TargetDraw(1, "player"),))
        [two] = spell_effects(CHOOSE_TWO)
        self.assertEqual((two.min, two.max), (2, 2))
        self.assertEqual(two.modes[0], (TargetLoseLife(3, "opponent"),))
        [both] = spell_effects(BOTH)
        self.assertEqual((both.min, both.max), (1, 2))
        self.assertEqual(spell_effects(Card(name="x", oracle_text="Target player gains 4 life."))[0], TargetGainLife(4, "player"))

    def test_unsupported_modes_leave_the_card_unsupported(self):
        for text in ("Choose one —\n• Destroy target artifact.\n• Tap all creatures your opponents control.",
                     "Choose one —\n• Draw a card.\n• You gain 1 life.\nEntwine {2}",
                     "Choose one —\nDraw a card."):
            self.assertIsNone(spell_effects(Card(name="x", oracle_text=text)), text)

    def test_report(self):
        for card in (CHOOSE_ONE, CHOOSE_TWO, BOTH):
            self.assertEqual(unsupported_lines(card), [], card.name)
        broken = Card(name="Cryptic", type_line="Instant", oracle_text="Choose one —\n• Draw a card.\n• Tap all creatures.")
        self.assertEqual(unsupported_lines(broken), ["• Tap all creatures."])

    def test_choose_one(self):
        game, _, _ = table(cast_policy("You gain 3 life."))
        seat = game.seats[0]
        seat.hand = [CHOOSE_ONE]
        seat.battlefield = lands(2)
        game.seats[1].battlefield = [Permanent(RELIC)]
        game._priority_round(seat)
        self.assertEqual((seat.life, len(game.seats[1].battlefield)), (43, 1))  # the artifact survived

    def test_a_mode_without_a_legal_target_is_not_offered(self):
        game, players = table3(cast_policy(0))
        seat = game.seats[0]
        seat.hand = [CHOOSE_ONE]
        seat.battlefield = lands(2)  # no artifact anywhere
        game._priority_round(seat)
        options = next(o for p, o in players[0].prompts if p.startswith(MODE_PROMPT))
        self.assertEqual(options, ["Target player draws a card.", "You gain 3 life."])

    def test_choose_two_asks_twice_and_resolves_in_printed_order(self):
        game, players = table3(cast_policy("Draw a card.", "Target opponent loses 3 life."))
        seat = game.seats[0]
        seat.hand = [CHOOSE_TWO]
        seat.battlefield = lands(4)
        game._priority_round(seat)
        prompts = [o for p, o in players[0].prompts if p.startswith(MODE_PROMPT)]
        self.assertEqual(len(prompts), 2)
        self.assertNotIn("Draw a card.", prompts[1])  # one mode can't be chosen twice
        self.assertEqual(len(seat.hand), 1)
        self.assertEqual(sorted(s.life for s in game.seats[1:]), [37, 40])  # one opponent, chosen by the target prompt

    def test_one_or_both_can_stop_after_one(self):
        game, players = table3(cast_policy("You gain 2 life.", DONE_MODES))
        seat = game.seats[0]
        seat.hand = [BOTH]
        seat.battlefield = [Permanent(RELIC)] + lands(2)
        game.seats[1].battlefield = [Permanent(RELIC)]
        game._priority_round(seat)
        prompts = [o for p, o in players[0].prompts if p.startswith(MODE_PROMPT)]
        self.assertNotIn(DONE_MODES, prompts[0])  # must choose at least one
        self.assertIn(DONE_MODES, prompts[1])
        self.assertEqual(seat.life, 42)
        self.assertEqual(len(game.seats[1].battlefield), 1)  # the artifact mode wasn't chosen

    def test_one_or_both_with_both(self):
        game, _ = table3(cast_policy(0, 0))
        seat = game.seats[0]
        seat.hand = [BOTH]
        seat.battlefield = lands(2)
        game.seats[1].battlefield = [Permanent(RELIC)]
        game._priority_round(seat)
        self.assertEqual((seat.life, game.seats[1].battlefield), (42, []))

    def test_not_castable_without_enough_usable_modes(self):
        game, _ = table3()
        seat = game.seats[0]
        seat.hand = [Card(name="Needs two", mana_cost="{1}", type_line="Instant",
                          oracle_text="Choose two —\n• Destroy target artifact.\n• Destroy target enchantment.\n• You gain 1 life.")]
        seat.battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(RELIC)]
        self.assertIn(CAST + "Needs two", game.legal_actions(seat))  # artifact + lifegain are usable
        game.seats[1].battlefield = []
        seat.hand = [Card(name="Needs two", mana_cost="{1}", type_line="Instant",
                          oracle_text="Choose two —\n• Destroy target artifact.\n• Destroy target enchantment.")]
        self.assertEqual(game.legal_actions(seat), [PASS])

    def test_target_player_effects(self):
        game, _ = table3()
        seat = game.seats[0]
        seat.hand = [CHOOSE_ONE]
        seat.battlefield = lands(2)
        draw_mode, cast = cast_policy("Target player draws a card."), pick(CAST, "Player: B")
        seat.player.policy = lambda prompt, options: (draw_mode(prompt, options) if prompt.startswith(MODE_PROMPT)
                                                      else cast(prompt, options))
        game._priority_round(seat)
        self.assertEqual(len(game.seats[1].hand), 1)


if __name__ == "__main__":
    unittest.main()
