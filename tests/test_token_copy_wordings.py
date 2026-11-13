"""Token copies in four more wordings, from the cards' real Oracle text: Skyclave Relic's two tapped copies of itself when kicked,
Littjara Mirrorlake's copy with an additional +1/+1 counter, Kindred Charge's copy of each creature of a chosen type and Hate Mirage's
copies of up to two creatures an opponent controls (both with haste, exiled at the next end step)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.families.copying import CopyChanges, copy_counters
from infernal_machine.effects.outcomes import _parse, _split_sentences
from infernal_machine.game import CAST, CHOOSE_TYPE_PROMPT, KICKER_PROMPT, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, ELF, OGRE, RELIC, activate, lands, real, run_stack, table3

SKYCLAVE_RELIC = real("Skyclave Relic", "{3}", "Artifact", "Kicker {3}\nIndestructible\nWhen this artifact enters, if it was kicked, create "
                      "two tapped tokens that are copies of this artifact.\n{T}: Add one mana of any color.")
MIRRORLAKE = real("Littjara Mirrorlake", "", "Land", "This land enters tapped.\n{T}: Add {U}.\n{2}{G}{G}{U}, {T}, Sacrifice this land: "
                  "Create a token that's a copy of target creature you control, except it enters with an additional +1/+1 counter on it. "
                  "Activate only as a sorcery.")
KINDRED_CHARGE = real("Kindred Charge", "{4}{R}{R}", "Sorcery", "Choose a creature type. For each creature you control of the chosen type, "
                      "create a token that's a copy of that creature. Those tokens gain haste. Exile them at the beginning of the next end "
                      "step.", colors=("R",))
HATE_MIRAGE = real("Hate Mirage", "{3}{R}", "Sorcery", "Choose up to two target creatures you don't control. For each of those creatures, "
                   "create a token that's a copy of that creature. Those tokens gain haste. Exile them at the beginning of the next end "
                   "step.", colors=("R",))


def tokens(seat):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token")]


def end_step(game, seat):
    game.step = "end"
    game._turn_based_actions(seat)
    run_stack(game)


def kicking(kick):
    def policy(prompt, options):
        return (0 if kick else 1) if KICKER_PROMPT.matches(prompt) else 0
    return policy


class TokenCopyWordingTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SKYCLAVE_RELIC, MIRRORLAKE, KINDRED_CHARGE, HATE_MIRAGE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_skyclave_relic_kicked_makes_two_tapped_copies_of_itself(self):
        for kick, made in ((True, 2), (False, 0)):
            game, _ = table3(kicking(kick))
            a = game.seats[0]
            a.battlefield, a.hand = lands(6), [SKYCLAVE_RELIC]
            game._perform(a, CAST + SKYCLAVE_RELIC.name)
            run_stack(game)
            copies = tokens(a)
            self.assertEqual(([p.card.name for p in copies], all(p.tapped for p in copies)), (["Skyclave Relic"] * made, True), kick)

    def test_littjara_mirrorlake_copies_a_creature_with_a_counter(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [*lands(5), Permanent(MIRRORLAKE), bear]
        activate(game, a, "Littjara Mirrorlake")
        [copy] = tokens(a)
        self.assertEqual((copy.card.name, copy.counters.get("+1/+1"), any(p.card.name == "Littjara Mirrorlake" for p in a.battlefield)),
                         ("Bear", 1, False))

    def test_tapped_copies_are_read_only_of_the_card_itself(self):
        self.assertIsNone(_parse(_split_sentences("Create two tapped tokens that are copies of target creature you control.")))

    def test_only_a_creature_copy_gets_the_counter(self):
        changes = CopyChanges(extra_counters="1")
        self.assertEqual((copy_counters(BEAR, changes), copy_counters(RELIC, changes), copy_counters(BEAR, None)), ((1, "+1/+1"), None, None))

    def test_kindred_charge_copies_each_creature_of_the_chosen_type_until_the_end_step(self):
        def elves(prompt, options):
            return options.index("Elf") if CHOOSE_TYPE_PROMPT.matches(prompt) else 0
        game, _ = table3(elves)
        a = game.seats[0]
        a.battlefield, a.hand = [*lands(6), Permanent(ELF), Permanent(ELF), Permanent(BEAR)], [KINDRED_CHARGE]
        game._perform(a, CAST + KINDRED_CHARGE.name)
        run_stack(game)
        made = tokens(a)
        self.assertEqual(([p.card.name for p in made], all(game.has_keyword(p, "haste") for p in made)), (["Elf", "Elf"], True))
        end_step(game, a)
        self.assertEqual(tokens(a), [])

    def test_hate_mirage_copies_up_to_two_creatures_you_dont_control(self):
        offered = []

        def first(prompt, options):
            if TARGET_PROMPT.matches(prompt):
                offered.extend(options)
            return 0
        game, _ = table3(first)
        a, b = game.seats[0], game.seats[1]
        a.battlefield, a.hand = [*lands(4), Permanent(ELF)], [HATE_MIRAGE]
        b.battlefield = [Permanent(BEAR), Permanent(OGRE)]
        game._perform(a, CAST + HATE_MIRAGE.name)
        run_stack(game)
        made = tokens(a)
        self.assertEqual((sorted(p.card.name for p in made), all(game.has_keyword(p, "haste") for p in made), len(b.battlefield)),
                         (["Bear", "Ogre"], True, 2))  # two different creatures, theirs still there
        self.assertFalse(any("Elf" in o for o in offered))  # its own creature is never a choice
        end_step(game, a)
        self.assertEqual(tokens(a), [])


if __name__ == "__main__":
    unittest.main()
