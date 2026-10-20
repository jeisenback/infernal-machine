"""Where a clone may find what it copies ("You may have this creature enter as a copy of ..."): a creature card in a graveyard, a
permanent that entered this turn, a creature of a mana value the mana spent allows; and the except clauses that make the copy
legendary or snow, an artifact, a 4/4 black Zombie, or not legendary "if that permanent is legendary". Lines are the cards' own
Oracle text."""

import dataclasses
import unittest

from infernal_machine.game import CAST, CLONE_PROMPT, NOT_A_COPY, PLAY_LAND, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, PASS, lands, real, run_stack, table

BODY_DOUBLE = real("Body Double", "{4}{U}", "Creature — Shapeshifter", "You may have Body Double enter as a copy of any creature card in a graveyard.",
                   "0", "0")
PROTEGE = real("Sakashima's Protege", "{4}{U}{U}", "Creature — Shapeshifter",
               "Flash\nCascade (When you cast this spell, exile cards from the top of your library until you exile a nonland card that costs "
               "less. You may cast it without paying its mana cost. Put the exiled cards on the bottom in a random order.)\nYou may have "
               "Sakashima's Protege enter as a copy of any permanent that entered this turn.", "3", "1")
MOCKINGBIRD = real("Mockingbird", "{X}{U}", "Creature — Bird Bard",
                   "Flying\nYou may have Mockingbird enter the battlefield as a copy of any creature on the battlefield with mana value less "
                   "than or equal to the amount of mana spent to cast Mockingbird, except it's a Bird in addition to its other types and it "
                   "has flying.", "1", "1")
EFFIGY = real("Machine God's Effigy", "{4}", "Artifact",
              "You may have Machine God's Effigy enter as a copy of any creature on the battlefield, except it's an artifact and it has "
              "\"{T}: Add {U}.\" (It's not a creature.)\n{T}: Add {U}.")
MORITTE = real("Moritte of the Frost", "{2}{G}{U}{U}", "Legendary Snow Creature — Shapeshifter",
               "Changeling (This card is every creature type.)\nYou may have Moritte of the Frost enter as a copy of a permanent you control, "
               "except it's legendary and snow in addition to its other types and, if it's a creature, it enters with two additional +1/+1 "
               "counters on it and has changeling.", "0", "0")
SPARK_DOUBLE = real("Spark Double", "{3}{U}", "Creature — Illusion",
                    "You may have Spark Double enter as a copy of a creature or planeswalker you control, except it enters with an additional "
                    "+1/+1 counter on it if it's a creature, it enters with an additional loyalty counter on it if it's a planeswalker, and it "
                    "isn't legendary if that permanent is legendary.", "0", "0")
ECHOING_DEEPS = real("Echoing Deeps", "", "Land — Cave",
                     "You may have Echoing Deeps enter tapped as a copy of any land card in a graveyard, except it's a Cave in addition to its "
                     "other types.\n{T}: Add {C}.")
SAKASHIMA = real("Sakashima the Impostor", "{2}{U}{U}", "Legendary Creature — Human Rogue",
                 "You may have Sakashima the Impostor enter as a copy of any creature on the battlefield, except its name is Sakashima the "
                 "Impostor, it's legendary in addition to its other types, and it has \"{2}{U}{U}: Return this creature to its owner's hand "
                 "at the beginning of the next end step.\"", "3", "1")
HERO = real("Test Hero", "{1}{W}", "Legendary Creature — Human Knight", "Vigilance", "2", "2")
BIG = real("Big Thing", "{3}{G}", "Creature — Beast", "", "4", "4")
CAVE = real("Test Cave", "", "Land", "{T}: Add {G}.")


def choosing(wanted, x=None):
    """Policy: cast the card (with `x`), copy the permanent whose label starts with `wanted` (or nothing, for None), else pass."""
    def policy(prompt, options):
        if CLONE_PROMPT.matches(prompt):
            if wanted is None:
                return options.index(NOT_A_COPY)
            return next(i for i, option in enumerate(options) if option.startswith(wanted))
        if X_PROMPT.matches(prompt):
            return options.index(str(x))
        return next((i for i, option in enumerate(options) if option.startswith((CAST, PLAY_LAND))), options.index(PASS) if PASS in options else 0)
    return policy


def enter(card, mine=(), theirs=(), wanted=None, graveyards=((), ()), x=None, n=6):
    game, _, _ = table(choosing(wanted, x))
    a, b = game.seats
    a.hand = [card]
    a.battlefield = lands(n) + [p if isinstance(p, Permanent) else Permanent(p) for p in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    a.graveyard, b.graveyard = list(graveyards[0]), list(graveyards[1])
    game._priority_round(a)
    run_stack(game)
    return game, a, b


def entered(seat, name):
    return next(p for p in seat.battlefield if p.card.name == name and p.real_card is not None)


def offered(card, mine=(), theirs=(), graveyards=((), ()), x=None):
    """The labels the clone prompt offers."""
    seen = []
    game, _, _ = table(lambda prompt, options: seen.extend(options) or (options.index(NOT_A_COPY) if CLONE_PROMPT.matches(prompt) else
                                                                        options.index(str(x)) if X_PROMPT.matches(prompt) else
                                                                        choosing(None)(prompt, options)))
    a, b = game.seats
    a.hand = [card]
    a.battlefield = lands(6) + [p if isinstance(p, Permanent) else Permanent(p) for p in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    a.graveyard, b.graveyard = list(graveyards[0]), list(graveyards[1])
    game._priority_round(a)
    run_stack(game)
    return [label.split(" (")[0] for label in seen if label != NOT_A_COPY and not label.startswith((CAST, PLAY_LAND)) and label != PASS and not label.isdigit()]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (BODY_DOUBLE, PROTEGE, MOCKINGBIRD, EFFIGY, MORITTE, SPARK_DOUBLE, ECHOING_DEEPS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_granted_ability_the_engine_does_not_understand_leaves_the_line_unsupported(self):
        self.assertEqual(len(unsupported_lines(SAKASHIMA)), 1)


class WhereToCopyFromTests(unittest.TestCase):
    def test_body_double_copies_a_creature_card_in_any_graveyard_and_leaves_the_card_there(self):
        game, a, b = enter(BODY_DOUBLE, graveyards=([BEAR], [HERO]), wanted="Test Hero")
        copy = entered(a, "Test Hero")
        self.assertEqual((copy.card.type_line, copy.real_card.name), ("Legendary Creature — Human Knight", "Body Double"))
        self.assertEqual(([c.name for c in a.graveyard], [c.name for c in b.graveyard]), (["Bear"], ["Test Hero"]))

    def test_body_double_is_offered_only_creature_cards(self):
        self.assertEqual(offered(BODY_DOUBLE, graveyards=([BEAR, CAVE], [])), ["Bear"])
        self.assertEqual(offered(BODY_DOUBLE, mine=[OGRE]), [])  # a creature on the battlefield is not a card in a graveyard

    def test_the_protege_copies_only_a_permanent_that_entered_this_turn(self):
        game, _, _ = table()
        fresh, old = Permanent(BEAR, entered_turn=game.turn), Permanent(OGRE, entered_turn=game.turn - 1)
        self.assertEqual(offered(PROTEGE, mine=[fresh, old]), ["Bear 2/2"])

    def test_mockingbird_copies_a_creature_whose_mana_value_the_mana_spent_allows(self):
        self.assertEqual(offered(MOCKINGBIRD, mine=[BEAR], theirs=[BIG], x=1), ["Bear 2/2"])  # {1}{U}: two mana, a 4-drop is too much
        self.assertEqual(sorted(offered(MOCKINGBIRD, mine=[BEAR], theirs=[BIG], x=3)), ["Bear 2/2", "Big Thing 4/4"])
        game, a, _ = enter(MOCKINGBIRD, theirs=[BIG], wanted="Big Thing", x=3)
        copy = entered(a, "Big Thing")
        self.assertEqual(copy.card.type_line, "Creature — Beast Bird")
        self.assertTrue(game.has_keyword(copy, "flying"))

    def test_echoing_deeps_enters_tapped_as_a_cave_copy_of_a_land_card_in_a_graveyard(self):
        game, a, _ = enter(ECHOING_DEEPS, graveyards=([], [CAVE]), wanted="Test Cave")
        copy = entered(a, "Test Cave")
        self.assertEqual((copy.card.type_line, copy.tapped), ("Land — Cave", True))


class ExceptClauseTests(unittest.TestCase):
    def test_the_effigy_is_an_artifact_copy_with_a_mana_ability(self):
        game, a, _ = enter(EFFIGY, mine=[BEAR], wanted="Bear")
        copy = entered(a, "Bear")
        self.assertEqual(copy.card.type_line, "Artifact Creature — Test")
        self.assertTrue(copy.card.oracle_text.endswith("{T}: Add {U}."))

    def test_moritte_is_a_legendary_snow_copy_with_two_more_counters_on_a_creature(self):
        game, a, _ = enter(MORITTE, mine=[BEAR], wanted="Bear")
        copy = entered(a, "Bear")
        self.assertTrue(copy.card.type_line.startswith("Legendary Snow Creature — Test "), copy.card.type_line)
        self.assertIn("Zombie", copy.card.type_line.split())  # changeling: every creature type
        self.assertEqual(copy.counters, {"+1/+1": 2})
        self.assertIn("Changeling", copy.card.oracle_text)
        game, a, _ = enter(MORITTE, mine=[CAVE], wanted="Test Cave")
        copy = entered(a, "Test Cave")
        self.assertEqual((copy.card.type_line, copy.counters), ("Legendary Snow Land", {}))

    def test_spark_double_copies_a_legend_without_the_supertype_and_with_a_counter(self):
        game, a, _ = enter(SPARK_DOUBLE, mine=[HERO], wanted="Test Hero")
        copy = entered(a, "Test Hero")
        self.assertEqual((copy.card.type_line, copy.counters), ("Creature — Human Knight", {"+1/+1": 1}))
        game, a, _ = enter(SPARK_DOUBLE, mine=[BEAR], wanted="Bear")
        self.assertEqual(entered(a, "Bear").card.type_line, "Creature — Test")  # not legendary to begin with: unchanged


if __name__ == "__main__":
    unittest.main()
