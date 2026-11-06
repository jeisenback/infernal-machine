"""Standard's Dimir Excruciator and Dimir Reanimator decks, from their cards' real Oracle text: Deadly Cover-Up (collect evidence; exile
every card with a name), Doomsday Excruciator (each player keeps only the bottom six cards of their library), Overlord of the Balemurk
(Impending; mill four and return a non-Avatar creature or planeswalker card) and Uldaros Theorix (cast copies of exiled cards)."""

import unittest

from infernal_machine.game import CAST, EVIDENCE_NONE, EVIDENCE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, fire, lands, real, run_stack, script, table3

COVER_UP = real("Deadly Cover-Up", "{3}{B}{B}", "Sorcery", "As an additional cost to cast this spell, you may collect evidence 6.\nDestroy "
                "all creatures. If evidence was collected, exile a card from an opponent's graveyard. Then search its owner's graveyard, "
                "hand, and library for any number of cards with that name and exile them. That player shuffles, then draws a card for each "
                "card exiled from their hand this way.", colors=("B",))
EXCRUCIATOR = real("Doomsday Excruciator", "{B}{B}{B}{B}{B}{B}", "Creature — Demon", "Flying\nWhen this creature enters, if it was cast, "
                   "each player exiles all but the bottom six cards of their library face down.\nAt the beginning of your upkeep, draw a "
                   "card.", "6", "6", colors=("B",))
OVERLORD = real("Overlord of the Balemurk", "{3}{B}{B}", "Enchantment Creature — Avatar Horror", "Impending 5—{1}{B} (If you cast this spell "
                "for its impending cost, it enters with five time counters and isn't a creature until the last is removed. At the beginning "
                "of your end step, remove a time counter from it.)\nWhenever this permanent enters or attacks, mill four cards, then you may "
                "return a non-Avatar creature card or a planeswalker card from your graveyard to your hand.", "5", "5", colors=("B",))
ULDAROS = real("Uldaros Theorix", "{3}{U}{B}{B}", "Legendary Creature — Elder Sphinx", "Flying\nWhen Uldaros Theorix enters, if you cast him, "
               "exile up to one target nonland card of each card type from your graveyard. Copy those cards. You may cast any number of "
               "spells with total mana value 6 or less from among the copies without paying their mana costs. (Permanent spells cast this "
               "way become tokens.)", "5", "5", colors=("B", "U"))
BEAR = real("Bear", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
AVATAR = real("Avatar", "{2}{B}", "Creature — Avatar", "", "3", "3", colors=("B",))
GIANT = real("Giant", "{4}{R}", "Creature — Giant", "", "5", "5", colors=("R",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
CITADEL = real("Darksteel Citadel", "", "Artifact Land", "Indestructible\n{T}: Add {C}.")
RAMPAGE = real("Rampage", "{4}{R}", "Sorcery", "Rampage deals 5 damage to each opponent.", colors=("R",))


def table(*answers, battlefield=(), hand=(), graveyard=(), library=None):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield, a.hand, a.graveyard = list(battlefield), list(hand), list(graveyard)
    for seat in game.seats:
        seat.library = list(library) if library is not None else [FOREST] * 10
    return game, a, b, c


def named(seat, card):
    return [p for p in seat.battlefield if p.card.name == card.name]


class StandardDimirGraveyardTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (COVER_UP, EXCRUCIATOR, OVERLORD, ULDAROS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_overlord_cast_for_impending_is_no_creature_until_its_time_counters_are_gone(self):
        game, a, _, _ = table("Bear", battlefield=lands(2), hand=[OVERLORD], library=[BEAR, AVATAR, FOREST, FOREST, FOREST])
        game._perform(a, CAST + "Overlord of the Balemurk")
        run_stack(game)
        overlord = named(a, OVERLORD)[0]
        self.assertEqual((overlord.counters, "Creature" in overlord.card.type_line), ({"time": 5}, False))
        self.assertEqual([c.name for c in a.hand], ["Bear"])  # milled four, took the Bear back
        for left in (4, 3, 2, 1, 0):
            game.step = "end"
            game._turn_based_actions(a)
            self.assertEqual(overlord.counters.get("time", 0), left)
        self.assertIn("Creature", overlord.card.type_line)

    def test_the_end_step_leaves_alone_a_stand_in_card_without_time_counters(self):
        stand_in = Permanent(AVATAR, real_card=BEAR)  # a permanent showing another card (a Room's door, a Saga with an ability)
        game, a, _, _ = table(battlefield=[stand_in])
        game.step = "end"
        game._turn_based_actions(a)
        self.assertIs(stand_in.card, AVATAR)

    def test_overlord_cast_for_its_mana_cost_is_a_creature_at_once(self):
        game, a, _, _ = table("Pay", "Take none", battlefield=lands(5), hand=[OVERLORD])
        game._perform(a, CAST + "Overlord of the Balemurk")
        run_stack(game)
        overlord = named(a, OVERLORD)[0]
        self.assertEqual((overlord.counters.get("time"), "Creature" in overlord.card.type_line), (None, True))

    def test_overlord_cannot_return_an_avatar(self):
        overlord = Permanent(OVERLORD)
        game, a, _, _ = table(battlefield=[overlord], library=[AVATAR, FOREST, FOREST, FOREST])
        asked = []
        choose = a.player.choose
        a.player.choose = lambda prompt, options: asked.append(list(options)) or choose(prompt, options)
        fire(game, a, overlord, "enters")
        self.assertNotIn("Avatar", [o for options in asked for o in options])
        self.assertEqual(a.hand, [])

    def test_doomsday_excruciator_cast_leaves_each_library_six_cards(self):
        game, a, b, c = table(battlefield=lands(6), hand=[EXCRUCIATOR])
        game._perform(a, CAST + "Doomsday Excruciator")
        run_stack(game)
        self.assertEqual([len(s.library) for s in (a, b, c)], [6, 6, 6])
        self.assertEqual(len(b.exile), 4)

    def test_doomsday_excruciator_put_onto_the_battlefield_exiles_nothing(self):
        excruciator = Permanent(EXCRUCIATOR)
        game, a, b, _ = table(battlefield=[excruciator])
        fire(game, a, excruciator, "enters")
        self.assertEqual(len(b.library), 10)

    def test_deadly_cover_up_with_evidence_exiles_every_card_with_the_name(self):
        game, a, b, _ = table("Giant", "Giant", "Bear", battlefield=lands(5) + [Permanent(BEAR)], hand=[COVER_UP],
                              graveyard=[GIANT, OPT])
        b.battlefield, b.graveyard, b.hand, b.library = [Permanent(GIANT)], [BEAR], [BEAR, OPT], [BEAR, FOREST, FOREST]
        game._perform(a, CAST + "Deadly Cover-Up")
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield + b.battlefield if "Creature" in p.card.type_line], [])
        self.assertEqual(sorted(c.name for c in a.exile), ["Giant", "Opt"])  # the evidence: the Giant once, then the Opt
        self.assertEqual([c.name for c in b.exile].count("Bear"), 3)  # from the graveyard, the hand and the library
        self.assertNotIn("Bear", [c.name for c in b.hand + b.library + b.graveyard])
        self.assertEqual(len(b.hand), 2)  # the Opt, and a card for the Bear exiled from the hand

    def test_deadly_cover_up_without_evidence_only_destroys(self):
        game, a, b, _ = table(EVIDENCE_NONE, battlefield=lands(5), hand=[COVER_UP], graveyard=[GIANT, OPT])
        b.battlefield, b.graveyard = [Permanent(BEAR)], [BEAR]
        game._perform(a, CAST + "Deadly Cover-Up")
        run_stack(game)
        self.assertEqual((b.battlefield, b.graveyard, b.exile), ([], [BEAR, BEAR], []))
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Deadly Cover-Up", "Giant", "Opt"])

    def test_deadly_cover_up_asks_for_no_evidence_it_cannot_collect(self):
        game, a, b, _ = table(battlefield=lands(5), hand=[COVER_UP], graveyard=[OPT, BEAR])  # total mana value 3
        asked = []
        choose = a.player.choose
        a.player.choose = lambda prompt, options: asked.append(prompt) or choose(prompt, options)
        game._perform(a, CAST + "Deadly Cover-Up")
        run_stack(game)
        self.assertFalse(any(EVIDENCE_PROMPT.matches(p) for p in asked))

    def test_doomsday_excruciator_keeps_a_short_library_whole(self):
        game, a, b, _ = table(battlefield=lands(6), hand=[EXCRUCIATOR])
        b.library = [FOREST] * 4
        game._perform(a, CAST + "Doomsday Excruciator")
        run_stack(game)
        self.assertEqual((len(b.library), b.exile), (4, []))

    def test_uldaros_theorix_casts_copies_up_to_six_mana_value(self):
        game, a, b, _ = table("Bear", "Rampage", "Bear", "Rampage", battlefield=lands(7), hand=[ULDAROS], graveyard=[BEAR, RAMPAGE, FOREST])
        game._perform(a, CAST + "Uldaros Theorix")
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.exile), ["Bear", "Rampage"])
        self.assertEqual(len(named(a, BEAR)), 1)  # a token copy
        self.assertEqual(b.life, 40)  # Rampage (5) did not fit in the 4 left after the Bear (2)
        self.assertEqual([c.name for c in a.graveyard], ["Forest"])

    def test_uldaros_theorix_does_not_offer_an_artifact_land(self):
        game, a, _, _ = table(battlefield=lands(7), hand=[ULDAROS], graveyard=[CITADEL])
        asked = []
        choose = a.player.choose
        a.player.choose = lambda prompt, options: asked.append(list(options)) or choose(prompt, options)
        game._perform(a, CAST + "Uldaros Theorix")
        run_stack(game)
        self.assertNotIn("Darksteel Citadel", [o for options in asked for o in options])
        self.assertEqual(a.graveyard, [CITADEL])

    def test_uldaros_theorix_put_onto_the_battlefield_does_nothing(self):
        uldaros = Permanent(ULDAROS)
        game, a, _, _ = table(battlefield=[uldaros], graveyard=[BEAR])
        fire(game, a, uldaros, "enters")
        self.assertEqual(a.graveyard, [BEAR])


if __name__ == "__main__":
    unittest.main()
