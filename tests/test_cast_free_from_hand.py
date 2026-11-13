"""Casting without paying the mana cost, from the cards' real Oracle text: Maelstrom Archangel's "you may cast a spell from your hand"
(any spell, any mana value), Omnispell Adept's "an instant or sorcery spell" (only those), and Impulsivity's "target instant or sorcery
card from a graveyard" (anyone's), exiled instead of going back to a graveyard."""

import unittest

from infernal_machine.effects.families.copying import CAST_COPY_PROMPT
from infernal_machine.effects.families.exile_and_return import FREE_CAST_PROMPT
from infernal_machine.game import DECLINE_CAST, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, DIVINATION, FOREST, activate, enter, fire, lands, real, run_stack, table3

ARCHANGEL = real("Maelstrom Archangel", "{W}{U}{B}{R}{G}", "Creature — Angel", "Flying\nWhenever this creature deals combat damage to a "
                 "player, you may cast a spell from your hand without paying its mana cost.", "5", "5", colors=tuple("WUBRG"))
ADEPT = real("Omnispell Adept", "{4}{U}", "Creature — Human Wizard", "{2}{U}, {T}: You may cast an instant or sorcery spell from your hand "
             "without paying its mana cost.", "3", "4", colors=("U",))
IMPULSIVITY = real("Impulsivity", "{6}{R}", "Creature — Elemental Incarnation", "When this creature enters, you may cast target instant or "
                   "sorcery card from a graveyard without paying its mana cost. If that spell would be put into a graveyard, exile it "
                   "instead.\nEncore {7}{R}{R} ({7}{R}{R}, Exile this card from your graveyard: For each opponent, create a token copy "
                   "that attacks that opponent this turn if able. They gain haste. Sacrifice them at the beginning of the next end step. "
                   "Activate only as a sorcery.)", "7", "5", colors=("R",))
BIG = real("Colossus", "{9}", "Artifact Creature — Golem", "", "9", "9")


def offered_then_first(seen):
    def policy(prompt, options):
        if FREE_CAST_PROMPT.matches(prompt):
            seen.extend(options)
        return 0
    return policy


class CastFreeFromHandTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ARCHANGEL, ADEPT, IMPULSIVITY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_maelstrom_archangel_casts_any_spell_from_the_hand(self):
        seen = []
        game, _ = table3(offered_then_first(seen))
        a = game.seats[0]
        angel = Permanent(ARCHANGEL)
        a.battlefield, a.hand = [angel], [BIG, FOREST]
        fire(game, a, angel, "combat_damage_to_player")
        self.assertEqual((seen, [p.card.name for p in a.battlefield], a.hand), (["Colossus", DECLINE_CAST], ["Maelstrom Archangel", "Colossus"],
                                                                                [FOREST]))

    def test_omnispell_adept_offers_only_instants_and_sorceries(self):
        seen = []
        game, _ = table3(offered_then_first(seen))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [*lands(3), Permanent(ADEPT)], [BEAR, DIVINATION], [FOREST] * 5
        activate(game, a, "Omnispell Adept")
        self.assertEqual((seen, [c.name for c in a.hand], len(a.library)), (["Divination", DECLINE_CAST], ["Bear", "Forest", "Forest"], 3))

    def test_impulsivity_casts_an_opponents_sorcery_and_exiles_it(self):
        def cast_it(prompt, options):
            if TARGET_PROMPT.matches(prompt):
                assert not any("Bear" in o for o in options), options  # only an instant or sorcery card
            return 0
        game, _ = table3(cast_it)
        a, b = game.seats[0], game.seats[1]
        a.library, b.graveyard = [FOREST] * 5, [BEAR, DIVINATION]
        enter(game, a, IMPULSIVITY)
        run_stack(game)
        self.assertEqual((len(a.hand), b.graveyard, [c.name for c in b.exile]), (2, [BEAR], ["Divination"]))

    def test_impulsivity_may_decline(self):
        def decline(prompt, options):
            return 1 if CAST_COPY_PROMPT.matches(prompt) else 0
        game, _ = table3(decline)
        a, b = game.seats[0], game.seats[1]
        a.library, b.graveyard = [FOREST] * 5, [DIVINATION]
        enter(game, a, IMPULSIVITY)
        run_stack(game)
        self.assertEqual((a.hand, b.graveyard), ([], [DIVINATION]))


if __name__ == "__main__":
    unittest.main()
