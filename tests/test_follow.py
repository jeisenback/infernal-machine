"""Follow-up sentences as data (follow.py, issue #437): the machinery on toy effects, and the converted tables on the real cards that use
them. (The whole pool reads the same as before: the coverage audit's output is identical before and after.)"""

import dataclasses
import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.effects.common import _split_sentences
from infernal_machine.effects.follow import Follow, Follows, set_fields
from infernal_machine.effects.outcomes import Counter, GainControl, PumpSource, _parse
from tests.helpers import real


@dataclasses.dataclass(frozen=True)
class Draw:
    count: int = 1
    more: int = 0
    more_if: str = ""


@dataclasses.dataclass(frozen=True)
class Gain:
    life: int = 1


@dataclasses.dataclass(frozen=True)
class Instead:
    count: int
    condition: str


@dataclasses.dataclass(frozen=True)
class Absorbed:
    pass


ROWS = Follows(Follow(Instead, Draw, set_fields(more=lambda m: m.count, more_if=lambda m: m.condition)),
               Follow(Absorbed, Gain))


class MachineryTests(unittest.TestCase):
    def test_a_marker_changes_the_effect_before_it_and_disappears(self):
        self.assertEqual(ROWS([Draw(), Instead(2, "lands")]), [Draw(1, 2, "lands")])

    def test_a_marker_with_no_make_is_just_absorbed(self):
        self.assertEqual(ROWS([Gain(3), Absorbed()]), [Gain(3)])

    def test_effects_that_are_not_markers_pass_through_in_order(self):
        self.assertEqual(ROWS([Gain(1), Draw(), Gain(2)]), [Gain(1), Draw(), Gain(2)])

    def test_a_marker_with_nothing_before_it_rejects_the_line(self):
        self.assertIsNone(ROWS([Instead(2, "x")]))

    def test_a_marker_after_the_wrong_effect_rejects_the_line(self):
        self.assertIsNone(ROWS([Gain(), Instead(2, "x")]))
        self.assertIsNone(ROWS([Draw(), Absorbed()]))

    def test_the_marker_changes_only_the_effect_directly_before_it(self):
        self.assertEqual(ROWS([Draw(1), Draw(5), Instead(3, "c")]), [Draw(1), Draw(5, 3, "c")])
        self.assertIsNone(ROWS([Draw(), Gain(), Instead(3, "c")]))

    def test_fits_decides_beyond_the_type(self):
        only_when_plain = Follows(Follow(Instead, Draw, set_fields(more=lambda m: m.count), fits=lambda previous, marker: not previous.more))
        self.assertEqual(only_when_plain([Draw(), Instead(2, "")]), [Draw(1, 2)])
        self.assertIsNone(only_when_plain([Draw(1, 4), Instead(2, "")]))

    def test_a_non_strict_row_leaves_a_marker_that_does_not_fit_as_an_effect(self):
        lenient = Follows(Follow(Instead, Draw, set_fields(more=lambda m: m.count), strict=False))
        self.assertEqual(lenient([Gain(), Instead(2, "")]), [Gain(), Instead(2, "")])
        self.assertEqual(lenient([Draw(), Instead(2, "")]), [Draw(1, 2)])

    def test_step_says_folded_rejected_or_not_about_it(self):
        merged = [Draw()]
        self.assertTrue(ROWS.step(merged, Instead(2, "")))
        self.assertIsNone(ROWS.step(merged, Gain()))
        self.assertFalse(ROWS.step([], Instead(2, "")))


REVERBERATE = real("Reverberate", "{R}{R}", "Instant", "Copy target instant or sorcery spell. You may choose new targets for the copy.")
MANA_DRAIN = real("Mana Drain", "{U}{U}", "Instant", "Counter target spell. At the beginning of your next main phase, add an amount of {C} equal to that spell's mana value.")
DISSIPATE = real("Dissipate", "{1}{U}{U}", "Instant", "Counter target spell. If that spell is countered this way, exile it instead of putting it into its owner's graveyard.")
REBOUND = real("Rebound", "{1}{U}", "Instant", "Change the target of target spell that targets only a player. The new target must be a player.")
RESONATOR = real("Strionic Resonator", "{2}", "Artifact",
                 '{2}, {T}: Copy target triggered ability you control. You may choose new targets for the copy. (A triggered ability uses the words '
                 '"when," "whenever," or "at.")')
TREASON = real("Act of Treason", "{2}{R}", "Sorcery", "Gain control of target creature until end of turn. Untap that creature. It gains haste until end of turn.")


class ConvertedTableTests(unittest.TestCase):
    def test_new_targets_are_folded_into_the_copy(self):
        [copy] = spell_effects(REVERBERATE)
        self.assertEqual((type(copy).__name__, copy.new_targets), ("CopySpell", True))

    def test_mana_drain_is_one_counter_that_gives_the_mana_later(self):
        [counter] = spell_effects(MANA_DRAIN)
        self.assertEqual((type(counter), counter.delayed_mana), (Counter, True))

    def test_exiling_it_instead_is_a_counter_that_exiles(self):
        [counter] = spell_effects(DISSIPATE)
        self.assertEqual((type(counter), counter.exile), (Counter, True))

    def test_threaten_untaps_the_creature_it_takes_and_gives_it_haste(self):
        control, haste = spell_effects(TREASON)
        self.assertEqual((type(control), control.untap), (GainControl, True))
        self.assertIsInstance(haste, PumpSource)  # (the haste sentence reaches the row's pass as an effect only later: as it always did)

    def test_the_new_target_must_be_folded_into_the_change_of_target(self):
        [change] = spell_effects(REBOUND)
        self.assertEqual((type(change).__name__, change.to), ("ChangeTarget", "player"))

    def test_a_second_new_target_sentence_after_one_that_has_it_is_not_understood(self):
        self.assertIsNone(_parse(_split_sentences("Change the target of target spell that targets only a player. The new target must be a player. "
                                                  "The new target must be a player.")))

    def test_new_targets_for_a_copied_triggered_ability(self):
        from infernal_machine.effects import activated_abilities

        [ability] = activated_abilities(RESONATOR)
        self.assertEqual((type(ability.effects[0]).__name__, ability.effects[0].new_targets), ("CopyTriggeredAbility", True))

    def test_cannot_be_regenerated_folds_into_a_destroy_and_stays_an_effect_otherwise(self):
        [destroy] = _parse(_split_sentences("Destroy target creature. It can't be regenerated."))
        self.assertTrue(destroy.no_regen)
        self.assertEqual([type(e).__name__ for e in _parse(_split_sentences("It can't be regenerated."))], ["CannotRegenerate"])

    def test_a_lone_second_sentence_is_not_understood(self):
        for text in ("You may choose new targets for the copy.", "Untap that creature.",
                     "At the beginning of your next main phase, add an amount of {C} equal to that spell's mana value.",
                     "If that spell is countered this way, exile it instead of putting it into its owner's graveyard."):
            self.assertIsNone(_parse(_split_sentences(text)), text)

    def test_the_haste_sentence_alone_is_a_pump_but_after_the_untap_it_is_folded(self):
        [pump] = _parse(_split_sentences("It gains haste until end of turn."))
        self.assertIsInstance(pump, PumpSource)
        # (a haste sentence after a control effect that did not untap stays an effect of its own)
        self.assertEqual([type(e) for e in _parse(_split_sentences("Gain control of target creature until end of turn. It gains haste until end of turn."))],
                         [GainControl, PumpSource])


if __name__ == "__main__":
    unittest.main()
