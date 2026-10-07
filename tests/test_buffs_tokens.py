import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (CANT_BLOCK, DoubleCounters, EachCreatesTokens, PumpEach, PumpX, PutCounters,
                                      RemoveCounters, TargetCreatesTokens, spell_effects, static_abilities,
                                      triggered_abilities)
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack


def spell(name, text, kind="Instant", cost="{U}"):
    return Card(name=name, mana_cost=cost, type_line=kind, oracle_text=text)


def cast_on(text, *permanents, hand=None, seats=None):
    """Cast a one-spell hand with `text`; the first prompt option for targets is taken. Returns the game."""
    game, _ = table3(pick(CAST))
    a = game.seats[0]
    a.hand, a.battlefield = [spell("Spell", text)], lands(3)
    for permanent in permanents:
        a.battlefield.append(permanent)
    game._priority_round(a)
    return game


class SetPowerAndToughnessTests(unittest.TestCase):
    def test_becomes_replaces_the_base(self):
        game = cast_on("Target creature becomes a 4/4 Dragon until end of turn.", bear := Permanent(BEAR))
        self.assertEqual((game.power(bear), game.toughness(bear)), (4, 4))

    def test_counters_and_bonuses_still_apply(self):
        game, _ = table3()
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        game.seats[0].battlefield = [bear]
        from infernal_machine.characteristics import Modifier
        game.modify_until_end_of_turn(bear, Modifier(2, 2))
        game.modify_until_end_of_turn(bear, Modifier(0, 0, frozenset(), (4, 4)))  # set after the bonus: order doesn't matter
        self.assertEqual((game.power(bear), game.toughness(bear)), (7, 7))

    def test_it_wears_off_at_end_of_turn(self):
        game = cast_on("Target creature has base power and toughness 0/1 until end of turn.", bear := Permanent(BEAR))
        self.assertEqual((game.power(bear), game.toughness(bear)), (0, 1))
        for permanent in [bear]:
            permanent.until_end_of_turn = []
        self.assertEqual((game.power(bear), game.toughness(bear)), (2, 2))

    def test_keywords_come_along(self):
        game = cast_on("Target creature becomes a 3/3 green Beast creature with flying until end of turn.",
                       bear := Permanent(BEAR))
        self.assertTrue(game.has_keyword(bear, "flying"))
        self.assertEqual(game.power(bear), 3)

    def test_the_report_accepts_them(self):
        for text in ("Target creature becomes a 4/4 Dragon until end of turn.",
                     "Target creature has base power and toughness 0/1 until end of turn."):
            self.assertEqual(unsupported_lines(spell("S", text)), [], text)


class OpponentsBuffTests(unittest.TestCase):
    def test_creatures_your_opponents_control(self):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        a.hand, a.battlefield = [spell("Fog of War", "Creatures your opponents control get -1/-1 until end of turn.")], lands(3)
        mine, theirs, small = Permanent(BEAR), Permanent(BEAR), Permanent(creature("Mite", 1, 1))
        a.battlefield.append(mine)
        b.battlefield, c.battlefield = [theirs], [small]
        game._priority_round(a)
        self.assertEqual((game.power(mine), game.power(theirs)), (2, 1))
        self.assertEqual(c.battlefield, [])  # the 1/1 died

    def test_parse(self):
        [effect] = spell_effects(spell("S", "Creatures your opponents control get -1/-1 until end of turn."))
        self.assertIsInstance(effect, PumpEach)
        self.assertTrue(effect.opponents)


class ScalingBuffTests(unittest.TestCase):
    def test_for_each_creature_you_control(self):
        game = cast_on("Target creature gets +1/+1 until end of turn for each creature you control.",
                       bear := Permanent(BEAR), Permanent(BEAR), Permanent(BEAR))
        self.assertEqual(game.power(bear), 2 + 3)  # three creatures

    def test_where_x_is(self):
        game = cast_on("Target creature gets -X/-X until end of turn, where X is the number of creatures you control.",
                       bear := Permanent(BEAR), Permanent(OGRE))
        self.assertEqual(bear in game.seats[0].battlefield, False)  # -2/-2 (X is two creatures) kills the Bear

    def test_only_power(self):
        [define, pump] = spell_effects(spell("S", "Target creature gets +1/+0 until end of turn for each creature you control."))
        self.assertEqual((pump.power, pump.toughness), (1, 0))
        self.assertIsInstance(pump, PumpX)

    def test_a_bigger_multiple(self):
        [define, pump] = spell_effects(spell("S", "Target creature gets +2/+2 until end of turn for each creature you control."))
        self.assertEqual((pump.power, pump.toughness), (2, 2))


class CounterTests(unittest.TestCase):
    def test_other_counter_types(self):
        game = cast_on("Put a charge counter on target artifact.", relic := Permanent(Card(name="Relic", type_line="Artifact")))
        self.assertEqual(relic.counters, {"charge": 1})

    def test_remove_some_all_or_everything(self):
        game, _ = table3()
        bear = Permanent(BEAR, counters={"+1/+1": 3, "charge": 2})
        game.seats[0].battlefield = [bear]
        RemoveCounters(1, "+1/+1", "creature").resolve(game, game.seats[0], bear)
        self.assertEqual(bear.counters, {"+1/+1": 2, "charge": 2})
        RemoveCounters(5, "+1/+1", "creature").resolve(game, game.seats[0], bear)  # only what is there
        self.assertEqual(bear.counters, {"charge": 2})
        RemoveCounters(None, None, "permanent").resolve(game, game.seats[0], bear)
        self.assertEqual(bear.counters, {})

    def test_remove_all_of_one_kind(self):
        game, _ = table3()
        bear = Permanent(BEAR, counters={"+1/+1": 3, "charge": 2})
        RemoveCounters(None, "charge", "creature").resolve(game, game.seats[0], bear)
        self.assertEqual(bear.counters, {"+1/+1": 3})

    def test_doubling(self):
        game, _ = table3()
        a = game.seats[0]
        one, two, none = Permanent(BEAR, counters={"+1/+1": 1}), Permanent(BEAR, counters={"+1/+1": 3}), Permanent(BEAR)
        a.battlefield = [one, two, none]
        DoubleCounters("+1/+1").resolve(game, a, None)
        self.assertEqual((one.counters, two.counters, none.counters), ({"+1/+1": 2}, {"+1/+1": 6}, {}))

    def test_for_each_counter_on_it(self):
        card = Card(name="Capacitor", mana_cost="{1}", type_line="Artifact",
                    oracle_text="When Capacitor enters, draw a card for each charge counter on it.")
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        [ability] = triggered_abilities(card)
        permanent = Permanent(card, counters={"charge": 3})
        a.battlefield = [permanent]
        game.trigger("enters", permanent, a)
        run_stack(game)
        self.assertEqual(len(a.hand), 3)

    def test_parse(self):
        self.assertEqual(spell_effects(spell("S", "Put two time counters on target permanent.")),
                         [PutCounters(2, "time", "permanent")])


class TokenTests(unittest.TestCase):
    def test_each_opponent_creates(self):
        game = cast_on("Each opponent creates a 1/1 white Spirit creature token with flying.")
        self.assertEqual([[p.card.name for p in s.battlefield if "Spirit" in p.card.name] for s in game.seats],
                         [[], ["Spirit"], ["Spirit"]])

    def test_each_player_creates(self):
        game = cast_on("Each player creates a Treasure token.")
        self.assertEqual([sum(p.card.name == "Treasure" for p in s.battlefield) for s in game.seats], [1, 1, 1])

    def test_target_opponent_creates(self):
        game, _ = table3(pick(CAST, "Player: B"))
        a = game.seats[0]
        a.hand, a.battlefield = [spell("Gift", "Target opponent creates a Treasure token.")], lands(2)
        game._priority_round(a)
        self.assertEqual([sum(p.card.name == "Treasure" for p in s.battlefield) for s in game.seats], [0, 1, 0])

    def test_parse(self):
        [effect] = spell_effects(spell("S", "Each opponent creates a Treasure token."))
        self.assertIsInstance(effect, EachCreatesTokens)
        [effect] = spell_effects(spell("S", "Target opponent creates a Treasure token."))
        self.assertIsInstance(effect, TargetCreatesTokens)

    def test_scaling_with_the_graveyard(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand = [spell("Raise", "Create a 2/2 black Zombie creature token for each creature card in your graveyard.", "Sorcery")]
        a.battlefield, a.graveyard = lands(3), [BEAR, OGRE, spell("Bolt", "Draw a card.")]
        game._priority_round(a)
        self.assertEqual(sum(p.card.name == "Zombie" for p in a.battlefield), 2)

    def test_a_token_that_cant_block(self):
        card = spell("Rats", 'Create two 1/1 black Rat creature tokens with "This creature can\'t block."', "Sorcery")
        self.assertEqual(unsupported_lines(card), [])
        game = cast_on(card.oracle_text)
        rats = [p for p in game.seats[0].battlefield if p.card.name == "Rat"]
        self.assertEqual(len(rats), 2)
        self.assertTrue(all(game.has_keyword(p, CANT_BLOCK) for p in rats))
        self.assertFalse(game.has_keyword(Permanent(BEAR), CANT_BLOCK))

    def test_the_static_line_is_read(self):
        card = Card(name="Rat", type_line="Token Creature — Rat", power="1", toughness="1",
                    oracle_text="This creature can't attack or block.")
        [static] = static_abilities(card)
        self.assertTrue(static.self_only)
