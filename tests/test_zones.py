import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (ExileFromGraveyard, LoseLife, ReturnAllToHand, ReturnFromGraveyard,
                                      ReturnToHand, SearchLibrary, spell_effects)
from infernal_machine.game import (CAST, COMMAND_ZONE_PROMPT, PASS, SEARCH_CARD_PROMPT, GraveyardTarget, Permanent)
from infernal_machine.report import unsupported_lines
from tests.test_effects import BEAR, BOLT, DARKSTEEL, FOREST, SOL_RING, lands, pick, table
from tests.test_exile import COMMANDER, OGRE
from tests.test_mass_effects import table3
from tests.test_tokens import RAISE
from tests.test_triggers import MULLDRIFTER

RIFT = Card(name="Cyclonic Rift", mana_cost="{1}{U}", type_line="Instant",
            oracle_text="Return target nonland permanent you don't control to its owner's hand.")
EVACUATION = Card(name="Evacuation", mana_cost="{3}{U}{U}", type_line="Instant",
                  oracle_text="Return all creatures to their owners' hands.")
RAISE_DEAD = Card(name="Raise Dead", mana_cost="{B}", type_line="Sorcery",
                  oracle_text="Return target creature card from your graveyard to your hand.")
ZOMBIFY = Card(name="Zombify", mana_cost="{3}{B}", type_line="Sorcery",
               oracle_text="Return target creature card from your graveyard to the battlefield.")
REANIMATE = Card(name="Reanimate", mana_cost="{B}", type_line="Sorcery",
                 oracle_text="Put target creature card from a graveyard onto the battlefield under your control.")
REGROWTH = Card(name="Regrowth", mana_cost="{1}{G}", type_line="Sorcery",
                oracle_text="Return target card from your graveyard to your hand.")
BOG = Card(name="Cleanse", mana_cost="{G}", type_line="Instant", oracle_text="Exile target card from a graveyard.")
DEMONIC = Card(name="Demonic Tutor", mana_cost="{1}{B}", type_line="Sorcery",
               oracle_text="Search your library for a card, put that card into your hand, then shuffle.")
WORLDLY = Card(name="Worldly Tutor", mana_cost="{G}", type_line="Instant",
               oracle_text="Search your library for a creature card, reveal it, then shuffle and put that card on top.")
VAMPIRIC = Card(name="Vampiric Tutor", mana_cost="{B}", type_line="Instant",
                oracle_text="Search your library for a card, then shuffle and put that card on top. You lose 2 life.")


def library_of(*cards):
    return list(cards) + [FOREST] * 5


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(RIFT), [ReturnToHand("nonland permanent you don't control")])
        self.assertEqual(spell_effects(EVACUATION), [ReturnAllToHand("creature")])
        self.assertEqual(spell_effects(RAISE_DEAD), [ReturnFromGraveyard("graveyard:creature:yours", "hand")])
        self.assertEqual(spell_effects(REGROWTH), [ReturnFromGraveyard("graveyard:card:yours", "hand")])
        self.assertEqual(spell_effects(ZOMBIFY), [ReturnFromGraveyard("graveyard:creature:yours", "battlefield")])
        self.assertEqual(spell_effects(REANIMATE), [ReturnFromGraveyard("graveyard:creature:any", "battlefield")])
        self.assertEqual(spell_effects(BOG), [ExileFromGraveyard("graveyard:card:any")])
        self.assertEqual(spell_effects(DEMONIC), [SearchLibrary("card", "hand", False)])
        self.assertEqual(spell_effects(WORLDLY), [SearchLibrary("creature", "top", True)])
        self.assertEqual(spell_effects(VAMPIRIC), [SearchLibrary("card", "top", False), LoseLife(2)])

    def test_variants_that_need_more_are_unsupported(self):
        for text in ("Return another target creature you control to its owner's hand.",
                     "Put target creature card from a graveyard onto the battlefield under your control. "
                     "You lose life equal to its mana value.",
                     "Search your library for a creature card with mana value 3 or less, put it into your hand, then shuffle."):
            self.assertIsNone(spell_effects(Card(name="x", oracle_text=text)), text)

    def test_report(self):
        for card in (RIFT, EVACUATION, RAISE_DEAD, ZOMBIFY, REANIMATE, BOG, DEMONIC, WORLDLY, VAMPIRIC):
            self.assertEqual(unsupported_lines(card), [], card.name)


class BounceTests(unittest.TestCase):
    def test_bounce_goes_to_the_owners_hand(self):
        game, _, _ = table(pick(CAST, "Grizzly"))
        game.seats[0].hand = [RIFT]
        game.seats[0].battlefield = lands(2)
        game.seats[1].battlefield = [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].battlefield, game.seats[1].hand, game.seats[1].graveyard), ([], [BEAR], []))

    def test_rift_cannot_target_your_own_or_lands(self):
        game, _, _ = table()
        game.seats[0].battlefield = [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(FOREST), Permanent(SOL_RING)]
        options = [label for label, _ in game.target_options("nonland permanent you don't control", game.seats[0])]
        self.assertEqual(options, ["Sol Ring (seat 1, #2)"])

    def test_bouncing_a_token_ends_it_and_bounced_creatures_can_re_enter(self):
        game, _, _ = table(pick(CAST, "Soldier"))
        game.seats[0].hand = [RIFT]
        game.seats[0].battlefield = lands(2)
        game.create_tokens(game.seats[1], spell_effects(RAISE)[0].token, 1)
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].battlefield, game.seats[1].hand), ([], []))

        # A bounced Mulldrifter can be recast and draws again.
        game.seats[1].hand = [MULLDRIFTER]
        game.seats[1].battlefield = lands(5)
        game.seats[1].player.policy = pick(CAST)
        game.active = 1
        game._priority_round(game.seats[1])
        self.assertEqual(len(game.seats[1].hand), 2)

    def test_commander_may_go_to_the_command_zone_instead_of_hand(self):
        game, _, b = table(pick(CAST, "Omnath"), pick("Command zone"))
        game.seats[0].hand = [RIFT]
        game.seats[0].battlefield = lands(2)
        game.seats[1].commander_names = {"Omnath"}
        game.seats[1].battlefield = [Permanent(COMMANDER)]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].command_zone, game.seats[1].hand), ([COMMANDER], []))
        self.assertIn((COMMAND_ZONE_PROMPT, ["Command zone", "Hand"]), b.prompts)

    def test_return_all(self):
        game, _ = table3(pick(CAST))
        game.seats[0].hand = [EVACUATION]
        game.seats[0].battlefield = lands(5) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(OGRE), Permanent(SOL_RING), Permanent(FOREST)]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[0].hand, game.seats[1].hand), ([BEAR], [OGRE]))
        self.assertEqual(sorted(p.card.name for p in game.seats[1].battlefield), ["Forest", "Sol Ring"])


class GraveyardTests(unittest.TestCase):
    def test_raise_dead_only_sees_your_graveyard_and_creature_cards(self):
        game, _, _ = table()
        game.seats[0].graveyard = [BEAR, BOLT]
        game.seats[1].graveyard = [OGRE]
        options = [label for label, _ in game.target_options("graveyard:creature:yours", game.seats[0])]
        self.assertEqual(options, ["Grizzly Bears (seat 0 graveyard)"])

    def test_raise_dead(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [RAISE_DEAD]
        game.seats[0].battlefield = lands(1)
        game.seats[0].graveyard = [BEAR]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[0].hand, game.seats[0].graveyard), ([BEAR], [RAISE_DEAD]))

    def test_no_legal_target_means_it_cannot_be_cast(self):
        game, _, _ = table()
        game.seats[0].hand = [RAISE_DEAD]
        game.seats[0].battlefield = lands(1)
        self.assertEqual(game.legal_actions(game.seats[0]), [PASS])

    def test_zombify_enters_with_summoning_sickness_and_triggers(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [ZOMBIFY]
        game.seats[0].battlefield = lands(4)
        game.seats[0].graveyard = [MULLDRIFTER]
        game._priority_round(game.seats[0])
        creature = game.seats[0].battlefield[-1]
        self.assertEqual((creature.card, creature.sick), (MULLDRIFTER, True))
        self.assertEqual(len(game.seats[0].hand), 2)  # its enters trigger drew two cards

    def test_reanimating_an_opponents_creature_keeps_it_theirs(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        game.seats[0].hand = [REANIMATE]
        game.seats[0].battlefield = lands(1)
        game.seats[1].graveyard = [OGRE]
        game._priority_round(game.seats[0])
        stolen = game.seats[0].battlefield[-1]
        self.assertEqual((stolen.card, game.seats[1].graveyard), (OGRE, []))
        game.destroy(stolen)
        self.assertEqual((game.seats[1].graveyard, [c for c in game.seats[0].graveyard if c is OGRE]), ([OGRE], []))

    def test_graveyard_target_gone_on_resolution(self):
        game, _, _ = table()
        game.seats[0].graveyard = [BEAR]
        [(_, target)] = game.target_options("graveyard:creature:yours", game.seats[0])
        self.assertTrue(game.is_legal_target("graveyard:creature:yours", target, game.seats[0]))
        game.seats[0].graveyard = [Card.from_dict(BEAR.to_dict())]  # a different but identical card
        self.assertIsNot(game.seats[0].graveyard[0], BEAR)
        self.assertTrue(game.is_legal_target("graveyard:creature:yours", target, game.seats[0]))
        game.seats[0].graveyard = []
        self.assertFalse(game.is_legal_target("graveyard:creature:yours", target, game.seats[0]))
        self.assertIsInstance(target, GraveyardTarget)

    def test_exile_from_a_graveyard(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        game.seats[0].hand = [BOG]
        game.seats[0].battlefield = lands(1)
        game.seats[1].graveyard = [BEAR, OGRE]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].graveyard, game.seats[1].exile), ([BEAR], [OGRE]))


class TutorTests(unittest.TestCase):
    def test_tutor_to_hand_is_private(self):
        game, players = table3(pick(CAST), None, None)
        seat = game.seats[0]
        seat.hand = [DEMONIC]
        seat.battlefield = lands(2)
        seat.library = library_of(MULLDRIFTER, BEAR)
        seat.player.policy = lambda prompt, options: (options.index("Grizzly Bears") if prompt == SEARCH_CARD_PROMPT
                                                       else pick(CAST)(prompt, options))
        game._priority_round(seat)
        self.assertEqual(seat.hand, [BEAR])
        self.assertNotIn(BEAR, seat.library)
        seen = [e for e in players[1].events if e["event"] == "searched"]
        self.assertEqual(seen, [{"event": "searched", "seat": 0, "found": True, "to": "hand"}])  # no card name
        own = [e for e in players[0].events if e["event"] == "searched"]
        self.assertEqual(own[0]["card"], "Grizzly Bears")

    def test_type_filter_lists_only_matching_cards(self):
        game, players = table3(pick(CAST))
        seat = game.seats[0]
        seat.hand = [WORLDLY]
        seat.battlefield = lands(1)
        seat.library = library_of(MULLDRIFTER, BEAR, BOLT)
        game._priority_round(seat)
        options = next(o for p, o in players[0].prompts if p == SEARCH_CARD_PROMPT)
        self.assertEqual(sorted(options), ["Grizzly Bears", "Mulldrifter"])

    def test_reveal_and_top_of_library(self):
        game, players = table3(pick(CAST))
        seat = game.seats[0]
        seat.hand = [WORLDLY]
        seat.battlefield = lands(1)
        seat.library = library_of(MULLDRIFTER, BEAR)
        game._priority_round(seat)
        self.assertEqual(seat.library[0].name, "Mulldrifter")  # the first option, put on top
        seen = [e for e in players[1].events if e["event"] == "searched"]
        self.assertEqual((seen[0]["card"], seen[0]["to"]), ("Mulldrifter", "top"))

    def test_vampiric_tutor_costs_life(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [VAMPIRIC]
        seat.battlefield = lands(1)
        seat.library = library_of(BOLT)
        game._priority_round(seat)
        self.assertEqual((seat.life, seat.library[0]), (38, BOLT))

    def test_nothing_to_find_still_shuffles_without_a_prompt(self):
        game, players = table3(pick(CAST))
        seat = game.seats[0]
        seat.hand = [WORLDLY]
        seat.battlefield = lands(1)
        seat.library = [FOREST] * 5
        game._priority_round(seat)
        self.assertEqual((len(seat.library), seat.hand), (5, []))
        self.assertFalse(any(p == SEARCH_CARD_PROMPT for p, _ in players[0].prompts))


if __name__ == "__main__":
    unittest.main()
