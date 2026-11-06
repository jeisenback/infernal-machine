"""Pauper Ruby Storm's missing cards (#648), from their real Oracle text: Glimpse the Impossible (what is still exiled at the next end
step becomes Spawn), Crossover Collaboration (a Treasure only with teamwork), Desperate Ritual (splice onto Arcane), Twinned Vision (two
cards when not cast from the hand; flashback with a discard), First Day of Class (a delayed trigger and Learn) and Seize the Storm (a token
whose size is defined by its own text)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, LEARN_PROMPT, SPLICE_PROMPT, TEAMWORK_NONE, YES_NO, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, MOUNTAIN, enter, lands, pick, real, run_stack, script, table3

GLIMPSE = real("Glimpse the Impossible", "{2}{R}", "Sorcery", "Exile the top three cards of your library. You may play those cards this turn. At "
               "the beginning of the next end step, if any of those cards remain exiled, put them into your graveyard, then create a 0/1 "
               "colorless Eldrazi Spawn creature token for each card put into your graveyard this way. Those tokens have \"Sacrifice this "
               "token: Add {C}.\"", colors=("R",))
CROSSOVER = real("Crossover Collaboration", "{2}{R}", "Instant", "Teamwork 2 (As an additional cost to cast this spell, you may tap any number "
                 "of creatures you control with total power 2 or more.)\nExile the top two cards of your library. Until the end of your next "
                 "turn, you may play those cards. If this spell was cast using teamwork, create a Treasure token. (It's an artifact with "
                 "\"{T}, Sacrifice this token: Add one mana of any color.\")", colors=("R",))
RITUAL = real("Desperate Ritual", "{1}{R}", "Instant — Arcane", "Add {R}{R}{R}.\nSplice onto Arcane {1}{R} (As you cast an Arcane spell, you "
              "may reveal this card from your hand and pay its splice cost. If you do, add this card's effects to that spell.)", colors=("R",))
VISION = real("Twinned Vision", "{1}{U/R}", "Instant", "Draw a card. If this spell wasn't cast from your hand, draw two cards instead.\n"
              "Flashback—{1}{U/R}{U/R}, Discard a card. (You may cast this card from your graveyard for its flashback cost. Then exile it.)",
              colors=("U", "R"))
CLASS = real("First Day of Class", "{1}{R}", "Instant", "Whenever a creature you control enters this turn, put a +1/+1 counter on it and it gains "
             "haste until end of turn.\nLearn. (You may reveal a Lesson card you own from outside the game and put it into your hand, or "
             "discard a card to draw a card.)", colors=("R",))
STORM = real("Seize the Storm", "{4}{R}", "Sorcery", "Create a red Elemental creature token with trample and \"This token's power and toughness "
             "are each equal to the number of instant and sorcery cards in your graveyard plus the number of cards with flashback you own in "
             "exile.\"\nFlashback {6}{R} (You may cast this card from your graveyard for its flashback cost. Then exile it.)", colors=("R",))
LESSON = real("Lesson Plan", "{1}{R}", "Sorcery — Lesson", "Draw a card.", colors=("R",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
ARCANE = real("Lava Spike", "{R}", "Sorcery — Arcane", "Lava Spike deals 3 damage to target player or planeswalker.", colors=("R",))


class PauperRubyStormTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GLIMPSE, CROSSOVER, RITUAL, VISION, CLASS, STORM):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_glimpse_the_impossible_turns_what_is_left_into_spawn_at_the_end_step(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(3, MOUNTAIN), [GLIMPSE], [MOUNTAIN, OPT, BEAR, OPT]
        game._perform(a, CAST + "Glimpse the Impossible")
        run_stack(game)
        game._perform(a, "Play land from exile: Mountain")  # one of the three is played from exile
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Glimpse the Impossible", "Opt"])
        self.assertEqual([p.card.name for p in a.battlefield].count("Eldrazi Spawn"), 2)
        self.assertEqual([c.name for c in a.library], ["Opt"])

    def test_crossover_collaboration_makes_a_treasure_only_with_teamwork(self):
        for answer, treasures in ((TEAMWORK_NONE, 0), ("Bear", 1)):
            game, _ = table3(pick(answer))
            a = game.seats[0]
            a.battlefield, a.hand, a.library = [*lands(3, MOUNTAIN), Permanent(BEAR)], [CROSSOVER], [OPT] * 3
            game._perform(a, CAST + "Crossover Collaboration")
            run_stack(game)
            self.assertEqual([p.card.name for p in a.battlefield].count("Treasure"), treasures, answer)

    def test_desperate_ritual_splices_its_mana_onto_an_arcane_spell(self):
        game, _ = table3(lambda prompt, options: (0 if SPLICE_PROMPT.matches(prompt) else options.index("Player: B (seat 1)")
                                                  if "Player: B (seat 1)" in options else 0))
        a = game.seats[0]
        a.battlefield, a.hand = lands(4, MOUNTAIN), [ARCANE, RITUAL]
        game._perform(a, CAST + "Lava Spike")  # {R} plus the splice cost {1}{R}
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], len(a.mana_pool)), (["Desperate Ritual"], 3))
        game2, _ = table3()
        b = game2.seats[0]
        b.battlefield, b.hand = lands(4, MOUNTAIN), [SHOCK, RITUAL]
        asked = []
        b.player.choose = lambda prompt, options: asked.append(prompt) or 0
        game2._perform(b, CAST + "Shock")  # not Arcane: no splice
        self.assertFalse(any(SPLICE_PROMPT.matches(p) for p in asked))

    def test_twinned_vision_draws_two_from_the_graveyard_after_a_discard(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(3, MOUNTAIN), [VISION, BEAR], [OPT] * 5
        game._perform(a, CAST + "Twinned Vision")
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Opt"])
        for p in a.battlefield:
            p.tapped = False
        game._perform(a, "Cast from graveyard: Twinned Vision")  # flashback, discarding the Bear
        run_stack(game)
        self.assertEqual((sorted(c.name for c in a.hand), [c.name for c in a.graveyard]), (["Opt", "Opt", "Opt"], ["Bear"]))

    def test_twinned_visions_flashback_needs_a_card_to_discard(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.graveyard = lands(3, MOUNTAIN), [], [VISION]
        self.assertNotIn("Cast from graveyard: Twinned Vision", game.legal_actions(a))

    def test_first_day_of_class_grows_creatures_entering_this_turn_and_learns(self):
        game, _ = table3(lambda prompt, options: options.index("Lesson Plan (outside the game)") if LEARN_PROMPT.matches(prompt) else 0)
        a = game.seats[0]
        a.battlefield, a.hand, a.sideboard = lands(2, MOUNTAIN), [CLASS], [LESSON]
        game._perform(a, CAST + "First Day of Class")
        run_stack(game)
        bear = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual((bear.counters.get("+1/+1"), game.has_keyword(bear, "haste"), [c.name for c in a.hand]), (1, True, ["Lesson Plan"]))
        game.step = "cleanup"
        game._turn_based_actions(a)  # the turn ends: so does the trigger
        later = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual(later.counters, {})

    def test_seize_the_storm_counts_spells_in_the_graveyard_and_flashback_cards_in_exile(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand = lands(5, MOUNTAIN), [STORM]
        a.graveyard, a.exile = [OPT, OPT, BEAR], [VISION, OPT]
        game._perform(a, CAST + "Seize the Storm")
        run_stack(game)
        token = next(p for p in a.battlefield if p.card.name == "Elemental")
        self.assertEqual((game.power(token), game.toughness(token), game.has_keyword(token, "trample")), (4, 4, True))  # 2 + 1 + the Storm


if __name__ == "__main__":
    unittest.main()
