import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import Counter, ExileTop, Flicker, spell_effects, triggered_abilities
from infernal_machine.game import CAST, CAST_EXILE, PASS, PLAY_EXILE, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, OGRE
from tests.test_effects import FOREST, lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack


def spell(name, text, kind="Instant", cost="{U}"):
    return Card(name=name, mana_cost=cost, type_line=kind, oracle_text=text)


EXILE_SPELL = spell("Spell Eater", "Exile target spell.")
DISSIPATE = spell("Dissipate", "Counter target spell. If that spell is countered this way, exile it instead of putting it "
                              "into its owner's graveyard.")
LIGHT = REAL["Reckless Impulse"]
IMPULSE = spell("Impulse", "Exile the top card of your library. You may play it this turn.", "Sorcery")
CLOUDSHIFT = spell("Cloudshift", "Exile target creature you control, then return that card to the battlefield under your "
                                 "control.")
EPHEMERATE = REAL["Momentary Blink"]
FLICKER = spell("Flicker Away", "Exile target creature. Return it to the battlefield under its owner's control at the "
                                "beginning of the next end step.")
TO_HAND = spell("Tuck Away", "Exile target creature. Return it to its owner's hand at the beginning of the next end step.")
FLICKERWISP = REAL["Flickerwisp"]
HOPPER = Card(name="Hopper", mana_cost="{1}", type_line="Creature — Test", power="1", toughness="1",
              oracle_text="When Hopper enters, you gain 2 life.")


class ParseTests(unittest.TestCase):
    def test_exiling_a_spell(self):
        self.assertEqual(spell_effects(EXILE_SPELL), [Counter("spell", exile=True)])
        self.assertEqual(spell_effects(DISSIPATE), [Counter("spell", exile=True)])
        self.assertEqual(spell_effects(spell("Cancel", "Counter target spell.")), [Counter("spell")])

    def test_exile_then_play(self):
        self.assertEqual(spell_effects(LIGHT), [ExileTop(2, "next turn")])
        self.assertEqual(spell_effects(IMPULSE), [ExileTop(1, "this turn")])
        self.assertEqual(spell_effects(spell("Mill", "Exile the top three cards of your library.", "Sorcery")), [ExileTop(3)])

    def test_flickers(self):
        self.assertEqual(spell_effects(CLOUDSHIFT), [Flicker("creature you control", under_owner=False)])
        self.assertEqual(spell_effects(EPHEMERATE), [Flicker("creature you control")])
        self.assertEqual(spell_effects(FLICKER), [Flicker("creature", "end_step")])
        self.assertEqual(spell_effects(TO_HAND), [Flicker("creature", "end_step", "hand")])
        [wisp] = triggered_abilities(FLICKERWISP)
        self.assertEqual(wisp.effects, (Flicker("permanent", "end_step", another=True),))

    def test_all_are_supported(self):
        for card in (EXILE_SPELL, DISSIPATE, LIGHT, IMPULSE, CLOUDSHIFT, EPHEMERATE, FLICKER, TO_HAND, FLICKERWISP):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_second_half_alone_is_not_understood(self):
        for text in ("Return it to the battlefield under its owner's control at the beginning of the next end step.",
                     "You may play it this turn.",
                     "If that spell is countered this way, exile it instead of putting it into its owner's graveyard.",
                     "Draw a card. You may play it this turn."):
            self.assertIsNone(spell_effects(spell("Half", text)), text)


class SpellExileTests(unittest.TestCase):
    def test_the_spell_is_exiled_not_put_in_the_graveyard(self):
        game, _ = table3()
        a, b, _ = game.seats
        item = StackItem(BEAR, b, [])
        game.stack.append(item)
        spell_effects(EXILE_SPELL)[0].resolve(game, a, item)
        self.assertEqual(([c.name for c in b.exile], b.graveyard, game.stack), (["Bear"], [], []))

    def test_a_plain_counter_still_uses_the_graveyard(self):
        game, _ = table3()
        a, b, _ = game.seats
        item = StackItem(BEAR, b, [])
        game.stack.append(item)
        spell_effects(spell("Cancel", "Counter target spell."))[0].resolve(game, a, item)
        self.assertEqual(([c.name for c in b.graveyard], b.exile), (["Bear"], []))


class FlickerTests(unittest.TestCase):
    def test_it_comes_back_as_a_new_object_without_counters_and_triggers_again(self):
        game, _ = table3()
        a = game.seats[0]
        hopper = Permanent(HOPPER, counters={"+1/+1": 2})
        a.battlefield = [hopper]
        game.flicker(hopper, a, "now", "battlefield", True)
        run_stack(game)
        [back] = a.battlefield
        self.assertEqual((back is hopper, back.counters, back.sick, a.life), (False, {}, True, 42))

    def test_under_your_control_or_its_owners(self):
        game, _ = table3()
        a, b, _ = game.seats
        theirs = Permanent(BEAR, owner=b)
        b.battlefield = [theirs]
        game.flicker(theirs, a, "now", "battlefield", under_owner=False)
        self.assertEqual(([p.card.name for p in a.battlefield], b.battlefield, b.exile), (["Bear"], [], []))
        game.flicker(a.battlefield[0], a, "now", "battlefield", under_owner=True)
        self.assertEqual(([p.card.name for p in b.battlefield], a.battlefield), (["Bear"], []))

    def test_a_token_does_not_come_back(self):
        game, _ = table3()
        a = game.seats[0]
        token = Permanent(Card(name="Goblin", type_line="Token Creature — Goblin", power="1", toughness="1"))
        a.battlefield = [token]
        game.flicker(token, a, "now", "battlefield", True)
        self.assertEqual((a.battlefield, a.exile), ([], []))

    def test_at_the_beginning_of_the_next_end_step(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game.flicker(bear, a, "end_step", "battlefield", True)
        self.assertEqual((a.battlefield, [c.name for c in a.exile]), ([], ["Bear"]))
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual(([p.card.name for p in a.battlefield], a.exile), (["Bear"], []))
        self.assertEqual(game.at_end_step, [])

    def test_in_the_end_step_it_waits_for_the_next_one(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game.step = "end"
        game.flicker(bear, a, "end_step", "battlefield", True)
        game._turn_based_actions(a)
        self.assertEqual(a.battlefield, [])  # this end step has already begun
        game.turn += 1
        game._turn_based_actions(a)
        self.assertEqual([p.card.name for p in a.battlefield], ["Bear"])

    def test_to_hand(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game.flicker(bear, a, "end_step", "hand", True)
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual(([c.name for c in a.hand], a.battlefield), (["Bear"], []))

    def test_cast_as_a_spell(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.hand, a.battlefield = [CLOUDSHIFT], lands(1) + [bear]
        game._priority_round(a)
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Bear"], ["Bear"])
        self.assertIsNot(next(p for p in a.battlefield if p.card.name == "Bear"), bear)


class ExileThenPlayTests(unittest.TestCase):
    def setup(self, play="this turn"):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST, BEAR, OGRE, FOREST]
        a.battlefield = lands(2)
        game.exile_top(a, 2, play)
        return game, a

    def test_the_cards_are_exiled_and_playable(self):
        game, a = self.setup()
        self.assertEqual(([c.name for c in a.exile], len(a.library)), (["Forest", "Bear"], 2))
        actions = game.legal_actions(a)
        self.assertIn(PLAY_EXILE + "Forest", actions)
        self.assertIn(CAST_EXILE + "Bear", actions)

    def test_playing_a_land_from_exile_uses_the_land_drop_once(self):
        game, a = self.setup()
        game._perform(a, PLAY_EXILE + "Forest")
        self.assertEqual((a.lands_played, a.battlefield[-1].card.name, [c.name for c in a.exile]), (1, "Forest", ["Bear"]))
        self.assertNotIn(PLAY_EXILE + "Forest", game.legal_actions(a))

    def test_casting_from_exile_uses_up_the_permission(self):
        game, a = self.setup()
        game._perform(a, CAST_EXILE + "Bear")
        self.assertEqual(game.stack[-1].card.name, "Bear")
        self.assertEqual(a.exile_play[0][0].name, "Forest")  # only the land is left to play
        self.assertNotIn(CAST_EXILE + "Bear", game.legal_actions(a))
        game._resolve(game.stack.pop())  # back to an empty stack, so it could be cast at sorcery speed again
        a.exile.append(BEAR)  # another Bear exiled later has no permission
        actions = game.legal_actions(a)
        self.assertIn(PLAY_EXILE + "Forest", actions)  # still able to play things from exile in general
        self.assertNotIn(CAST_EXILE + "Bear", actions)

    def test_this_turn_ends(self):
        game, a = self.setup()
        game.turn += 1
        self.assertFalse([x for x in game.legal_actions(a) if "exile" in x])

    def test_until_the_end_of_your_next_turn(self):
        game, a = self.setup("next turn")  # three seats, turn 2 now: their next turn is turn 5
        game.turn, game.active = 5, 0
        self.assertTrue([x for x in game.legal_actions(a) if "exile" in x])
        game.turn = 6
        self.assertFalse([x for x in game.legal_actions(a) if "exile" in x])

    def test_another_players_next_turn_comes_sooner(self):
        game, _ = table3()
        b = game.seats[1]
        b.library = [BEAR] * 3
        game.exile_top(b, 1, "next turn")  # seat 0 is active on turn 2: seat 1's next turn is turn 3
        self.assertEqual(b.exile_play[0][1], 3)

    def test_nothing_to_exile(self):
        game, _ = table3()
        game.seats[0].library = []
        game.exile_top(game.seats[0], 2, "this turn")
        self.assertEqual((game.seats[0].exile, game.seats[0].exile_play), ([], []))

    def test_a_spell_does_it(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.library = [BEAR, OGRE]
        a.hand, a.battlefield = [IMPULSE], lands(1)
        game._priority_round(a)
        self.assertEqual(([c.name for c in a.exile], [e[0].name for e in a.exile_play]), (["Bear"], ["Bear"]))

    def test_bots_play_exiled_cards(self):
        bot = BotPlayer("A", Deck([FOREST], [BEAR], []))
        self.assertEqual(bot.choose("Priority: main1", [PASS, CAST_EXILE + "Bear"]), 1)
        self.assertEqual(bot.choose("Priority: main1", [PASS, PLAY_EXILE + "Forest"]), 1)
