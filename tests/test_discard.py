import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import (Discard, EachDraw, TargetChooseDiscard, TargetDiscard, spell_effects,
                                      triggered_abilities)
from infernal_machine.game import CAST, CHOOSE_DISCARD_PROMPT, DISCARD_CARD_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import BOLT, FOREST, lands, pick
from tests.test_combat import BEAR
from tests.test_mass_effects import table3


def sorcery(name, text):
    return Card(name=name, mana_cost="{B}", type_line="Sorcery", oracle_text=text)


MIND_ROT = sorcery("Mind Rot", "Target player discards two cards.")
HYMN = sorcery("Hymn", "Target opponent discards two cards at random.")
SYPHON = sorcery("Syphon", "Each opponent discards a card.")
WINDFALL = sorcery("Test Windfall", "Each player discards their hand.")
WHEEL = sorcery("Wheel", "Each player discards their hand, then draws seven cards.")
LOOTING = sorcery("Looting", "Draw two cards, then discard two cards.")
DURESS = sorcery("Duress", "Target opponent reveals their hand. You choose a noncreature, nonland card from it. That "
                           "player discards that card.")
THOUGHTSEIZE = sorcery("Thoughtseize", "Target player reveals their hand. You choose a nonland card from it. That player "
                                       "discards that card. You lose 2 life.")
INQUISITION = sorcery("Test Inquisition", "Target player reveals their hand. You choose a nonland card with mana value 3 or "
                                     "less from it. That player discards that card.")
WRAITH = Card(name="Wraith", mana_cost="{B}", type_line="Enchantment",
              oracle_text="Whenever an opponent draws a card, that player discards a card.")
OGRE = Card(name="Ogre", mana_cost="{2}{R}", cmc=3, type_line="Creature — Ogre", power="3", toughness="3")
DRAGON = Card(name="Dragon", mana_cost="{4}{R}{R}", cmc=6, type_line="Creature — Dragon", power="5", toughness="5")
TITAN = Card(name="Titan", mana_cost="{5}", cmc=5, type_line="Artifact", oracle_text="")
CAST_THEN_FIRST = pick(CAST, "Player: B")


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(MIND_ROT), [TargetDiscard(2, "player")])
        self.assertEqual(spell_effects(HYMN), [TargetDiscard(2, "opponent", True)])
        self.assertEqual(spell_effects(SYPHON), [Discard(1, "each opponent")])
        self.assertEqual(spell_effects(WINDFALL), [Discard(None, "each player")])
        self.assertEqual(spell_effects(WHEEL), [Discard(None, "each player"), EachDraw(7)])
        self.assertEqual(spell_effects(LOOTING)[1], Discard(2, "you"))
        self.assertEqual(spell_effects(DURESS), [TargetChooseDiscard("opponent", ("creature", "land"), None)])
        self.assertEqual(spell_effects(INQUISITION), [TargetChooseDiscard("player", ("land",), 3)])
        self.assertEqual(spell_effects(THOUGHTSEIZE)[0], TargetChooseDiscard("player", ("land",), None))
        self.assertEqual(unsupported_lines(WRAITH), [])

    def test_all_are_supported(self):
        for card in (MIND_ROT, HYMN, SYPHON, WINDFALL, WHEEL, LOOTING, DURESS, THOUGHTSEIZE, INQUISITION):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_pieces_of_a_hand_attack_are_not_understood(self):
        for text in ("Target opponent reveals their hand.",
                     "You choose a nonland card from it. That player discards that card.",
                     "Target opponent reveals their hand. You choose a nonland card from it."):
            self.assertIsNone(spell_effects(sorcery("Half", text)), text)


class DiscardTests(unittest.TestCase):
    def test_the_player_chooses_what_to_discard(self):
        second = lambda prompt, options: 1 if prompt == DISCARD_CARD_PROMPT else (options.index("Pass") if "Pass" in options else 0)
        game, players = table3(pick(CAST, "Player: B"), second)
        a, b, _ = game.seats
        a.hand, a.battlefield = [MIND_ROT], lands(1)
        b.hand = [BEAR, BOLT, FOREST]
        game._priority_round(a)
        self.assertEqual([c.name for c in b.hand], ["Bear"])  # B's policy picks option 1 each time
        self.assertEqual([c.name for c in b.graveyard], ["Lightning Bolt", "Forest"])
        self.assertEqual(next(o for p, o in players[1].prompts if p == DISCARD_CARD_PROMPT), ["Bear", "Lightning Bolt", "Forest"])

    def test_discarding_more_than_the_hand_empties_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [BEAR]
        game.discard(a, 3)
        self.assertEqual((a.hand, [c.name for c in a.graveyard]), ([], ["Bear"]))

    def test_at_random_asks_nothing(self):
        game, players = table3()
        a = game.seats[0]
        a.hand = [BEAR, BOLT, FOREST, OGRE]
        game.discard(a, 2, random=True)
        self.assertEqual((len(a.hand), len(a.graveyard)), (2, 2))
        self.assertFalse([p for p, _ in players[0].prompts if p == DISCARD_CARD_PROMPT])

    def test_at_random_is_random(self):
        game, _ = table3()
        a = game.seats[0]
        seen = set()
        for _ in range(30):
            a.hand, a.graveyard = [BEAR, BOLT, FOREST, OGRE], []
            game.discard(a, 1, random=True)
            seen.add(a.graveyard[0].name)
        self.assertGreater(len(seen), 1)

    def test_the_whole_hand_is_discarded_without_choosing(self):
        game, players = table3()
        a, b, c = game.seats
        for seat in game.seats:
            seat.hand = [BEAR, BOLT]
        spell_effects(WINDFALL)[0].resolve(game, a, None)
        self.assertEqual([len(s.hand) for s in game.seats], [0, 0, 0])
        self.assertEqual([len(s.graveyard) for s in game.seats], [2, 2, 2])
        self.assertFalse([p for p, _ in players[0].prompts if p == DISCARD_CARD_PROMPT])

    def test_each_opponent_only(self):
        game, _ = table3()
        a, b, c = game.seats
        for seat in game.seats:
            seat.hand = [BEAR, BOLT]
        spell_effects(SYPHON)[0].resolve(game, a, None)
        self.assertEqual([len(s.hand) for s in game.seats], [2, 1, 1])

    def test_wheel_draws_seven_each(self):
        game, _ = table3()
        for seat in game.seats:
            seat.hand = [BEAR]
            seat.library = [FOREST] * 10
        for effect in spell_effects(WHEEL):
            effect.resolve(game, game.seats[0], None)
        self.assertEqual([len(s.hand) for s in game.seats], [7, 7, 7])
        self.assertEqual([len(s.graveyard) for s in game.seats], [1, 1, 1])

    def test_a_discard_is_public(self):
        game, players = table3()
        a = game.seats[0]
        a.hand = [BEAR]
        game.discard(a, 1)
        self.assertEqual(next(e for e in players[2].events if e["event"] == "discard"),
                         {"event": "discard", "seat": 0, "card": "Bear"})

    def test_a_trigger_makes_that_player_discard(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(WRAITH)]
        b.hand, b.library = [BEAR], [FOREST] * 3
        game.draw(b, 1)
        game._put_triggers_on_stack()
        while game.stack:
            game._resolve(game.stack.pop())
        self.assertEqual(len(b.hand), 1)  # drew a card, then discarded one
        self.assertEqual(len(b.graveyard), 1)


class ChooseDiscardTests(unittest.TestCase):
    def setUp(self):
        self.game, self.players = table3(pick(CAST, "Player: B"))
        self.a, self.b, _ = self.game.seats
        self.b.hand = [BEAR, BOLT, FOREST, TITAN]

    def cast(self, card):
        self.a.hand, self.a.battlefield = [card], lands(1)
        self.game._priority_round(self.a)

    def test_duress_takes_a_noncreature_nonland_card(self):
        self.cast(DURESS)
        self.assertEqual([c.name for c in self.b.graveyard], ["Lightning Bolt"])  # first of the eligible: Bolt, Titan
        options = next(o for p, o in self.players[0].prompts if p == CHOOSE_DISCARD_PROMPT)
        self.assertEqual(options, ["Lightning Bolt", "Titan"])

    def test_the_hand_is_revealed_to_everyone(self):
        self.cast(DURESS)
        event = next(e for e in self.players[2].events if e["event"] == "revealed_hand")
        self.assertEqual((event["seat"], event["cards"]), (1, ["Bear", "Lightning Bolt", "Forest", "Titan"]))

    def test_mana_value_limit(self):
        self.b.hand = [OGRE, DRAGON, TITAN]
        self.cast(INQUISITION)
        options = next(o for p, o in self.players[0].prompts if p == CHOOSE_DISCARD_PROMPT)
        self.assertEqual(options, ["Ogre"])

    def test_thoughtseize_costs_two_life(self):
        self.cast(THOUGHTSEIZE)
        self.assertEqual((self.a.life, len(self.b.hand)), (38, 3))

    def test_nothing_eligible_does_nothing_but_reveal(self):
        self.b.hand = [FOREST]
        self.cast(DURESS)
        self.assertEqual((len(self.b.hand), self.b.graveyard), (1, []))
        self.assertFalse([p for p, _ in self.players[0].prompts if p == CHOOSE_DISCARD_PROMPT])


class BotTests(unittest.TestCase):
    def test_bots_discard_their_worst_card_and_take_the_best(self):
        bot = BotPlayer("B", Deck([FOREST], [BEAR, DRAGON, FOREST], []))
        self.assertEqual(bot.choose(CHOOSE_DISCARD_PROMPT, ["Bear", "Dragon"]), 1)
        self.assertEqual(bot.choose(CHOOSE_DISCARD_PROMPT, ["Mystery", "Dragon"]), 1)
        self.assertEqual(bot.choose(CHOOSE_DISCARD_PROMPT, ["Mystery"]), 0)  # a card it doesn't know is still a card
        self.assertEqual(bot.choose(DISCARD_CARD_PROMPT, ["Dragon", "Forest", "Forest"]), 1)  # over half lands: a land goes
