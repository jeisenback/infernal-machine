"""Exile effects of issue #79: Vanishing Verse, Expressive Iteration, Reality Shift (manifest) and Dance with Calamity.

The issue cuts the long lines off with "..."; Expressive Iteration's last sentence and Dance with Calamity's last two are
completed from memory.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (DanceWithCalamity, Exile, ThreeWaySplit, TargetControllerManifests, spell_effects)
from infernal_machine.game import (CAST, DANCE_PROMPT, SPLIT_BOTTOM_PROMPT, SPLIT_HAND_PROMPT, TURN_UP, Permanent)
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, pick, run_stack, table

VANISHING_VERSE = Card(name="Vanishing Verse", mana_cost="{W}{B}", type_line="Instant", colors=("W", "B"), cmc=2,
                       oracle_text="Exile target monocolored permanent.")
EXPRESSIVE_ITERATION = Card(name="Expressive Iteration", mana_cost="{U}{R}", type_line="Sorcery", colors=("U", "R"), cmc=2,
                            oracle_text="Look at the top three cards of your library. Put one of them into your hand, put "
                                        "one of them on the bottom of your library, and exile one of them. You may play the "
                                        "exiled card this turn.")
REALITY_SHIFT = Card(name="Reality Shift", mana_cost="{1}{U}", type_line="Instant", colors=("U",), cmc=2,
                     oracle_text="Exile target creature. Its controller manifests the top card of their library.")
DANCE_WITH_CALAMITY = Card(name="Dance with Calamity", mana_cost="{3}{R}{R}", type_line="Sorcery", colors=("R",), cmc=5,
                           oracle_text="Shuffle your library. As many times as you choose, you may exile the top card of your "
                                       "library. If the total mana value of the cards exiled this way is 13 or less, you may "
                                       "cast any number of spells from among those cards without paying their mana costs.")


def card(name, cmc, kind="Artifact", colors=(), text=""):
    return Card(name=name, mana_cost="{%d}" % cmc if cmc else "", cmc=float(cmc), type_line=kind, colors=colors, oracle_text=text)


def supported(test, c):
    test.assertEqual(unsupported_lines(c), [], c.oracle_text)


def names(cards):
    return [c.name for c in cards]


class VanishingVerseTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(VANISHING_VERSE), [Exile("monocolored permanent")])
        supported(self, VANISHING_VERSE)

    def test_only_monocolored_permanents_can_be_chosen(self):
        green = Card(name="Green Bear", type_line="Creature — Bear", colors=("G",), power="2", toughness="2")
        gold = Card(name="Gold Bear", type_line="Creature — Bear", colors=("G", "W"), power="2", toughness="2")
        relic = Card(name="Relic", type_line="Artifact")
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.hand, a.battlefield = [VANISHING_VERSE], lands(2)
        b.battlefield = [Permanent(gold), Permanent(relic), Permanent(green)]
        options = [label for label, _ in game.target_options("monocolored permanent", a)]
        self.assertEqual(len(options), 1)
        self.assertIn("Green Bear", options[0])
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Gold Bear", "Relic"])


class ExpressiveIterationTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(EXPRESSIVE_ITERATION), [ThreeWaySplit(3, play=True)])
        supported(self, EXPRESSIVE_ITERATION)
        no_play = card("Split", 1, "Sorcery", text="Look at the top three cards of your library. Put one of them into your "
                                                   "hand, put one of them on the bottom of your library, and exile one of them.")
        self.assertEqual(spell_effects(no_play), [ThreeWaySplit(3, play=False)])

    def test_one_to_hand_one_to_the_bottom_one_exiled_and_playable_this_turn(self):
        top = [card("Alpha", 1), card("Beta", 2), card("Gamma", 3)]
        seen = []

        def policy(prompt, options):
            seen.append((prompt, list(options)))
            if SPLIT_HAND_PROMPT.matches(prompt):
                return options.index("Gamma")
            if SPLIT_BOTTOM_PROMPT.matches(prompt):
                return options.index("Alpha")
            return pick(CAST)(prompt, options)

        game, _, _ = table(policy)
        a = game.seats[0]
        a.library = top + a.library
        bottom_before = len(a.library)
        a.hand, a.battlefield = [EXPRESSIVE_ITERATION], lands(2)
        game._priority_round(a)
        self.assertEqual(names(a.hand), ["Gamma"])
        self.assertEqual(names(a.exile), ["Beta"])
        self.assertEqual(a.library[-1].name, "Alpha")
        self.assertEqual(len(a.library), bottom_before - 2)
        self.assertEqual([(c.name, until) for c, until in a.exile_play], [("Beta", game.turn)])
        self.assertIn(("Put which card on the bottom of your library? ", ["Alpha", "Beta"]),
                      [(p, o) for p, o in seen if p.startswith(SPLIT_BOTTOM_PROMPT)])

    def test_with_only_two_cards_the_hand_and_the_bottom_come_first_and_nothing_is_exiled(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.library = [card("Alpha", 1), card("Beta", 2)]
        a.hand, a.battlefield = [EXPRESSIVE_ITERATION], lands(2)
        game._priority_round(a)
        self.assertEqual((names(a.hand), names(a.exile), names(a.library)), (["Alpha"], [], ["Beta"]))


class ManifestTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(REALITY_SHIFT), [Exile("creature"), TargetControllerManifests()])
        supported(self, REALITY_SHIFT)

    def cast_on_bear(self, top):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.hand, a.battlefield = [REALITY_SHIFT], lands(2)
        b.battlefield = [Permanent(BEAR)]
        b.library = [top] + b.library
        game._priority_round(a)
        return game, a, b

    def test_its_controller_gets_the_top_card_face_down_as_a_2_by_2(self):
        ogre = Card(name="Hidden Ogre", mana_cost="{2}{R}", cmc=3.0, type_line="Creature — Ogre", power="5", toughness="5",
                    oracle_text="Trample")
        game, a, b = self.cast_on_bear(ogre)
        self.assertEqual(names(b.exile), ["Bear"])  # the Bear was exiled
        [manifest] = b.battlefield
        self.assertEqual((game.power(manifest), game.toughness(manifest), manifest.card.name), (2, 2, "Face-down creature"))
        self.assertFalse(game.has_keyword(manifest, "trample"))  # a face-down creature has no abilities
        self.assertEqual(manifest.real_card, ogre)

    def test_what_others_see_hides_the_card_but_its_controller_is_told(self):
        game, a, b = self.cast_on_bear(card("Secret", 1))
        mine, theirs = game.snapshot(b), game.snapshot(a)
        view_for = lambda snap: next(s for s in snap["seats"] if s["seat"] == 1)["battlefield"][0]
        self.assertEqual(view_for(mine)["face_down_as"], "Secret")
        self.assertIsNone(view_for(theirs)["face_down_as"])

    def test_it_goes_to_the_graveyard_as_the_real_card(self):
        game, a, b = self.cast_on_bear(card("Secret", 1))
        [manifest] = b.battlefield
        game._leave_battlefield(manifest, "dies")
        self.assertEqual(names(b.graveyard), ["Secret"])

    def test_a_manifested_creature_card_can_be_turned_up_for_its_mana_cost(self):
        ogre = Card(name="Hidden Ogre", mana_cost="{2}", cmc=2.0, type_line="Creature — Ogre", power="5", toughness="5")
        game, a, b = self.cast_on_bear(ogre)
        [manifest] = b.battlefield
        b.battlefield += lands(2)
        action = TURN_UP + game.label(manifest)
        self.assertIn(action, game.legal_actions(b))
        game._perform(b, action)
        self.assertEqual((manifest.card.name, game.power(manifest), manifest.real_card), ("Hidden Ogre", 5, None))
        self.assertNotIn(TURN_UP + game.label(manifest), game.legal_actions(b))

    def test_a_manifested_noncreature_or_an_unaffordable_one_cannot_be_turned_up(self):
        game, a, b = self.cast_on_bear(card("Relic", 1))  # an artifact
        [manifest] = b.battlefield
        b.battlefield += lands(3)
        self.assertEqual([x for x in game.legal_actions(b) if x.startswith(TURN_UP)], [])
        manifest.real_card = Card(name="Big", mana_cost="{9}", cmc=9.0, type_line="Creature — Giant", power="9", toughness="9")
        self.assertEqual([x for x in game.legal_actions(b) if x.startswith(TURN_UP)], [])

    def test_an_empty_library_manifests_nothing(self):
        game, _, _ = table()
        a = game.seats[0]
        a.library = []
        game.manifest(a)
        self.assertEqual(a.battlefield, [])


class DanceWithCalamityTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(DANCE_WITH_CALAMITY), [DanceWithCalamity(13)])
        supported(self, DANCE_WITH_CALAMITY)

    def play(self, top, exile_count, cast_answer):
        asked = []

        def policy(prompt, options):
            if DANCE_PROMPT.matches(prompt):
                asked.append(prompt)
                return 0 if len(asked) <= exile_count else 1
            if prompt.startswith("Cast "):  # for free
                return cast_answer(prompt)
            return pick(CAST)(prompt, options)

        game, _, _ = table(policy)
        game.rng.shuffle = lambda cards: None  # keep the order, so the top cards are the ones we set
        a = game.seats[0]
        a.library = list(top) + a.library
        a.hand, a.battlefield = [DANCE_WITH_CALAMITY], lands(5)
        game._priority_round(a)
        return game, a, asked

    def test_thirteen_or_less_lets_you_cast_them_all_for_free(self):
        top = [card("Alpha", 4), card("Beta", 4), card("Gamma", 5), card("Delta", 9)]
        game, a, asked = self.play(top, 3, lambda prompt: 0)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Alpha", "Beta", "Gamma"])
        self.assertEqual(len(asked), 4)  # three yeses and the no that stopped it
        self.assertEqual(a.exile, [])  # everything exiled was cast

    def test_over_thirteen_you_cast_nothing_and_they_stay_exiled(self):
        top = [card("Alpha", 6), card("Beta", 8)]
        game, a, asked = self.play(top, 2, lambda prompt: 0)
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], [])
        self.assertEqual(names(a.exile), ["Alpha", "Beta"])

    def test_you_may_cast_only_some_and_lands_are_never_cast(self):
        top = [card("Alpha", 2), card("Forest", 0, "Basic Land"), card("Beta", 3)]
        game, a, asked = self.play(top, 3, lambda prompt: 0 if "Alpha" in prompt else 1)
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], ["Alpha"])
        self.assertEqual(sorted(names(a.exile)), ["Beta", "Forest"])

    def test_the_prompt_tells_you_the_running_total(self):
        game, a, asked = self.play([card("Alpha", 4), card("Beta", 4)], 2, lambda prompt: 1)
        self.assertEqual(asked, [DANCE_PROMPT + "(0 exiled, total mana value 0)", DANCE_PROMPT + "(1 exiled, total mana value 4)",
                                 DANCE_PROMPT + "(2 exiled, total mana value 8)"][:len(asked)])

    def test_a_bot_stops_after_a_few_cards_even_when_they_cost_nothing(self):
        from infernal_machine.bot import BotPlayer
        from infernal_machine.cards import Deck
        bot = BotPlayer("Bot", Deck([card("Cmd", 3, "Legendary Creature — Test")], [card("Forest", 0, "Basic Land")] * 99, []))
        self.assertEqual(bot.choose(DANCE_PROMPT + "(0 exiled, total mana value 0)", ["Yes", "No"]), 0)
        self.assertEqual(bot.choose(DANCE_PROMPT + "(3 exiled, total mana value 8)", ["Yes", "No"]), 0)
        self.assertEqual(bot.choose(DANCE_PROMPT + "(4 exiled, total mana value 0)", ["Yes", "No"]), 1)  # a library of lands
        self.assertEqual(bot.choose(DANCE_PROMPT + "(2 exiled, total mana value 9)", ["Yes", "No"]), 1)

    def test_it_stops_when_the_library_is_empty(self):
        game, a, asked = self.play([card("Alpha", 1)], 99, lambda prompt: 1)
        self.assertGreaterEqual(len(asked), 1)
