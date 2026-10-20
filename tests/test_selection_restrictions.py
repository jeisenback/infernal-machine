import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Destroy, LoseLifeEqualToManaValue, ReturnFromGraveyard, ReturnToHand, SearchForLands,
                                      SearchLibrary, spell_effects)
from infernal_machine.effects.targets import _card_kind
from infernal_machine.game import CAST, NO_TARGET, SEARCH_CARD_PROMPT, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick, table

MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))


def creature(name, mana_value, text=""):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Test", power="2", toughness="2", cmc=float(mana_value),
                oracle_text=text)


DRAGON, OGRE, BEAR = creature("Dragon", 5), creature("Ogre", 3), creature("Bear", 2)
SPELL = Card(name="Cantrip", mana_cost="{1}", type_line="Sorcery", cmc=1.0, oracle_text="Draw a card.")


def sorcery(text):
    return Card(name="Spell", mana_cost="{1}", type_line="Sorcery", cmc=1.0, oracle_text=text)


def last_option(prompt, options):
    return len(options) - 1 if TARGET_PROMPT.matches(prompt) else (
        next(i for i, o in enumerate(options) if o.startswith(CAST)) if any(o.startswith(CAST) for o in options)
        else options.index("Pass"))


class KindTests(unittest.TestCase):
    def test_card_kind(self):
        self.assertEqual(_card_kind(None), "card")
        self.assertEqual(_card_kind("land card"), "land")
        self.assertEqual(_card_kind("creature card with mana value 3 or less"), "creature|mv<=3")
        self.assertEqual(_card_kind("card with mana value 4 or greater"), "card|mv>=4")
        self.assertEqual(_card_kind("permanent card with mana value 2"), "permanent|mv=2")

    def test_parse(self):
        self.assertEqual(spell_effects(sorcery("Search your library for a creature card with mana value 3 or less, "
                                               "reveal it, put it into your hand, then shuffle.")),
                         [SearchLibrary("creature|mv<=3", "hand", True)])
        self.assertEqual(spell_effects(sorcery("Return target creature card with mana value 2 or less from your "
                                               "graveyard to your hand.")),
                         [ReturnFromGraveyard("graveyard:creature|mv<=2:yours", "hand")])
        self.assertEqual(spell_effects(sorcery("Return another target creature to its owner's hand.")),
                         [ReturnToHand("creature", another=True, distinct=True)])
        self.assertEqual(spell_effects(sorcery("Return up to one target creature to its owner's hand.")),
                         [ReturnToHand("creature", optional_target=True)])
        self.assertEqual(spell_effects(sorcery("Destroy another target creature.")), [Destroy("creature", another=True)])
        self.assertEqual(spell_effects(sorcery("Search your library for a land card, put it onto the battlefield tapped, "
                                               "then shuffle.")), [SearchForLands(1, ("*",), 1, True, False)])
        self.assertEqual(spell_effects(sorcery("You lose life equal to its mana value.")), [LoseLifeEqualToManaValue()])

    def test_report(self):
        for text in ("Return up to one target creature to its owner's hand.",
                     "Search your library for a card with mana value 4, put it into your hand, then shuffle."):
            self.assertEqual(unsupported_lines(sorcery(text)), [], text)


class TutorAndRecursionTests(unittest.TestCase):
    def cast(self, text, library=(), graveyards=((), ()), policy=None):
        game, a_player, _ = table(policy or pick(CAST + "Spell"))
        a, b = game.seats
        a.hand = [sorcery(text)]
        a.battlefield = lands(2, MOUNTAIN)
        a.library = list(library)
        a.graveyard, b.graveyard = list(graveyards[0]), list(graveyards[1])
        game._priority_round(a)
        return game, a, b, a_player

    def test_the_search_only_offers_cards_with_that_mana_value(self):
        game, a, _, player = self.cast("Search your library for a creature card with mana value 3 or less, put it into "
                                       "your hand, then shuffle.", [DRAGON, SPELL, OGRE, BEAR])
        offered = [options for prompt, options in player.prompts if prompt == SEARCH_CARD_PROMPT]
        self.assertEqual(offered, [["Ogre", "Bear"]])
        self.assertEqual(len(a.hand), 1)

    def test_an_exact_mana_value_and_a_minimum(self):
        _, _, _, player = self.cast("Search your library for a card with mana value 3, put it into your hand, then shuffle.",
                                    [DRAGON, OGRE, BEAR])
        self.assertEqual([o for p, o in player.prompts if p == SEARCH_CARD_PROMPT], [["Ogre"]])
        _, _, _, player = self.cast("Search your library for a card with mana value 3 or greater, put it into your hand, "
                                    "then shuffle.", [DRAGON, OGRE, BEAR])
        self.assertEqual([o for p, o in player.prompts if p == SEARCH_CARD_PROMPT], [["Dragon", "Ogre"]])

    def test_nothing_matches(self):
        _, a, _, _ = self.cast("Search your library for a creature card with mana value 1 or less, put it into your hand, "
                               "then shuffle.", [DRAGON, OGRE])
        self.assertEqual(a.hand, [])

    def test_recursion_only_offers_cards_with_that_mana_value(self):
        game, a, b, player = self.cast("Return target creature card with mana value 2 or less from your graveyard to your "
                                       "hand.", graveyards=([DRAGON, BEAR], [creature("Elf", 1)]))
        offered = [options for prompt, options in player.prompts if TARGET_PROMPT.matches(prompt)]
        self.assertEqual(offered, [["Bear (seat 0 graveyard)"]])  # not the Dragon, not the opponent's Elf
        self.assertEqual([c.name for c in a.hand], ["Bear"])
        self.assertEqual([c.name for c in a.graveyard], ["Dragon", "Spell"])  # the spell itself ends up there too

    def test_reanimate_costs_life_equal_to_its_mana_value(self):
        game, a, b, _ = self.cast("Put target creature card from a graveyard onto the battlefield under your control. "
                                  "You lose life equal to its mana value.", graveyards=((), [DRAGON]))
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], ["Dragon"])
        self.assertEqual(a.life, 35)

    def test_a_land_card_onto_the_battlefield(self):
        garden = Card(name="Temple Garden", type_line="Land — Forest Plains", produced_mana=("G", "W"))
        _, a, _, _ = self.cast("Search your library for a land card, put it onto the battlefield tapped, then shuffle.",
                               [OGRE, garden])
        found = next(p for p in a.battlefield if p.card.name == "Temple Garden")
        self.assertTrue(found.tapped)


class AnotherAndUpToOneTests(unittest.TestCase):
    def test_another_target_is_never_the_source(self):
        game, _, _ = table(pick(CAST + "Bouncer"))
        a = game.seats[0]
        other = Permanent(BEAR)
        a.battlefield = [other] + lands(2, MOUNTAIN)
        a.hand = [creature("Bouncer", 1, "When CARDNAME enters, return another target creature to its owner's hand.")]
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Bouncer"])
        self.assertEqual([c.name for c in a.hand], ["Bear"])

    def test_with_nothing_else_to_target_nothing_happens(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.battlefield = lands(2, MOUNTAIN)
        a.hand = [creature("Bouncer", 1, "When CARDNAME enters, return another target creature to its owner's hand.")]
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Bouncer"])
        self.assertEqual(a.hand, [])

    def test_destroy_another_target_creature(self):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.battlefield = lands(2, MOUNTAIN)
        b.battlefield = [Permanent(BEAR)]
        a.hand = [creature("Slayer", 1, "When CARDNAME enters, destroy another target creature.")]
        game._priority_round(a)
        self.assertEqual((sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), b.battlefield),
                         (["Slayer"], []))

    def test_up_to_one_can_take_a_target(self):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.battlefield = lands(2, MOUNTAIN)
        b.battlefield = [Permanent(BEAR)]
        a.hand = [sorcery("Return up to one target creature to its owner's hand.")]
        game._priority_round(a)
        self.assertEqual((b.battlefield, [c.name for c in b.hand]), ([], ["Bear"]))

    def test_up_to_one_can_take_no_target(self):
        game, _, _ = table(last_option)
        a, b = game.seats
        a.battlefield = lands(2, MOUNTAIN)
        b.battlefield = [Permanent(BEAR)]
        a.hand = [sorcery("Return up to one target creature to its owner's hand.")]
        game._priority_round(a)
        self.assertEqual([p.card.name for p in b.battlefield], ["Bear"])
        self.assertEqual(a.hand, [])
        self.assertEqual(len(a.graveyard), 1)  # the spell was cast and resolved, not fizzled
        self.assertNotIn("fizzle", [e["event"] for e in game.seats[0].player.events])

    def test_up_to_one_can_be_cast_with_nothing_to_target(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = lands(2, MOUNTAIN)
        a.hand = [sorcery("Return up to one target creature to its owner's hand.")]
        self.assertIn(CAST + "Spell", game.legal_actions(a))

    def test_the_no_target_choice_is_offered_last(self):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.battlefield = lands(2, MOUNTAIN)
        b.battlefield = [Permanent(BEAR)]
        a.hand = [sorcery("Return up to one target creature to its owner's hand.")]
        game._priority_round(a)
        options = next(o for p, o in game.seats[0].player.prompts if p.startswith(TARGET_PROMPT))
        self.assertEqual(options[-1], NO_TARGET)


if __name__ == "__main__":
    unittest.main()
