import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import (Fight, FightFirst, Proliferate, ReturnWithCounter, spell_effects,
                                      triggered_abilities)
from infernal_machine.game import CAST, DONE, PROLIFERATE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import FOREST, lands, pick, table

FIGHT = REAL["Prey Upon"]
BITE = Card(name="Bite", mana_cost="{1}{G}", type_line="Sorcery",
            oracle_text="Target creature you control deals damage equal to its power to target creature you don't control.")
GROW = Card(name="Grow", mana_cost="{G}", type_line="Sorcery", oracle_text="Proliferate.")
OOZE = creature("Ooze", 2, 2, "Persist")
WOLF = creature("Wolf", 2, 2, "Undying")
SNAKE = creature("Viper", 1, 1, "Deathtouch")
PRIEST = creature("Priest", 2, 2, "Lifelink")
WALKER = Card(name="Walker", mana_cost="{3}", type_line="Planeswalker", loyalty="3")


def settle(game):
    game._priority_round(game.seats[0])


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


class FightTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(FIGHT), [FightFirst("creature you control"), Fight("creature you don't control")])
        self.assertEqual(spell_effects(BITE)[1], Fight("creature you don't control", one_sided=True))
        another = Card(name="x", oracle_text="Target creature fights another target creature.")
        self.assertEqual(spell_effects(another), [FightFirst("creature"), Fight("creature", another=True)])
        for card in (FIGHT, BITE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def cast(self, card, mine, theirs):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        a.hand = [card]
        a.battlefield = [Permanent(c) for c in mine] + lands(2, FOREST)
        b.battlefield = [Permanent(c) for c in theirs]
        game._priority_round(a)
        return a, b

    def test_each_deals_damage_equal_to_its_power_to_the_other(self):
        a, b = self.cast(FIGHT, [OGRE], [BEAR])
        self.assertEqual((names(a), names(b)), (["Ogre"], []))  # the Bear took 3, the Ogre took 2
        self.assertEqual(a.battlefield[0].damage, 2)

    def test_both_can_die(self):
        a, b = self.cast(FIGHT, [BEAR], [BEAR])
        self.assertEqual((names(a), names(b)), ([], []))

    def test_a_bite_is_one_sided(self):
        a, b = self.cast(BITE, [BEAR], [OGRE])
        self.assertEqual((names(a), names(b)), (["Bear"], ["Ogre"]))
        self.assertEqual(next(p for p in b.battlefield).damage, 2)
        self.assertEqual(next(p for p in a.battlefield if p.card.name == "Bear").damage, 0)

    def test_deathtouch_and_lifelink_apply(self):
        a, b = self.cast(FIGHT, [SNAKE], [OGRE])
        self.assertEqual((names(a), names(b)), ([], []))  # the Ogre's 3 damage kills the Viper; deathtouch kills the Ogre
        a, b = self.cast(FIGHT, [PRIEST], [BEAR])
        self.assertEqual(a.life, 42)

    def test_it_needs_both_targets(self):
        game, _, _ = table()
        a = game.seats[0]
        a.hand = [FIGHT]
        a.battlefield = [Permanent(BEAR)] + lands(2, FOREST)
        self.assertNotIn(CAST + "Fight", game.legal_actions(a))  # nothing to fight

    def test_a_missing_target_means_no_fight(self):
        game, _, _ = table()
        a, b = game.seats
        mine = Permanent(OGRE)
        a.battlefield = [mine]
        game.resolving_item = type("Item", (), {"carried": mine})()
        Fight("creature").resolve(game, a, None)
        Fight("creature", another=True).resolve(game, a, mine)  # the same creature isn't "another"
        game.resolving_item = None
        self.assertEqual(mine.damage, 0)

    def test_a_creature_that_left_does_not_fight(self):
        game, _, _ = table()
        a, b = game.seats
        mine, theirs = Permanent(OGRE), Permanent(BEAR)
        a.battlefield = [mine]
        b.battlefield = []
        game.fight(mine, theirs)
        self.assertEqual(mine.damage, 0)


class ProliferateTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(GROW), [Proliferate()])
        self.assertEqual(unsupported_lines(GROW), [])

    def setup(self, policy):
        game, player, _ = table(policy)
        a, b = game.seats
        counted = Permanent(BEAR)
        counted.counters = {"+1/+1": 1, "-1/-1": 2}
        plain = Permanent(OGRE)
        walker = Permanent(WALKER, loyalty=3)
        enemy = Permanent(OGRE)
        enemy.counters = {"-1/-1": 1}
        a.battlefield = [counted, plain, walker]
        b.battlefield = [enemy]
        return game, a, player, (counted, plain, walker, enemy)

    def test_everything_chosen_gets_one_more_of_each_kind(self):
        game, a, _, (counted, plain, walker, enemy) = self.setup(lambda prompt, options: 0)
        game.proliferate(a)
        self.assertEqual(counted.counters, {"+1/+1": 2, "-1/-1": 3})
        self.assertEqual((walker.loyalty, plain.counters, enemy.counters), (4, {}, {"-1/-1": 2}))

    def test_only_permanents_with_counters_are_offered(self):
        game, a, player, _ = self.setup(lambda prompt, options: len(options) - 1)
        game.proliferate(a)
        offered = [options for prompt, options in player.prompts if prompt == PROLIFERATE_PROMPT]
        self.assertEqual(len(offered), 1)
        self.assertEqual(len(offered[0]), 4)  # Bear, Walker, the opponent's Ogre, and Done
        self.assertEqual(offered[0][-1], DONE)

    def test_it_can_choose_none(self):
        game, a, _, (counted, _, walker, enemy) = self.setup(lambda prompt, options: len(options) - 1)
        game.proliferate(a)
        self.assertEqual((counted.counters, walker.loyalty, enemy.counters), ({"+1/+1": 1, "-1/-1": 2}, 3, {"-1/-1": 1}))

    def test_it_can_choose_some(self):
        game, a, _, (counted, _, walker, enemy) = self.setup(lambda prompt, options: 2 if len(options) == 4 else len(options) - 1)
        game.proliferate(a)  # the opponent's creature, then done
        self.assertEqual((counted.counters, walker.loyalty, enemy.counters), ({"+1/+1": 1, "-1/-1": 2}, 3, {"-1/-1": 2}))

    def test_the_bot_adds_counters_only_to_its_own_permanents(self):
        bot = BotPlayer("A", Deck([FOREST], [OGRE], []))
        bot._seat = 0
        self.assertEqual(bot.choose(PROLIFERATE_PROMPT, ["Bear 2/2 (seat 1, #1)", "Ogre 3/3 (seat 0, #1)", DONE]), 1)
        self.assertEqual(bot.choose(PROLIFERATE_PROMPT, ["Bear 2/2 (seat 1, #1)", DONE]), 1)


class PersistTests(unittest.TestCase):
    def kill(self, card, counters=None, token=False):
        game, _, _ = table()
        a = game.seats[0]
        if token:
            card = Card(name=card.name, type_line="Token " + card.type_line, power=card.power, toughness=card.toughness,
                        oracle_text=card.oracle_text)
        perm = Permanent(card)
        perm.counters = dict(counters or {})
        a.battlefield = [perm]
        game._leave_battlefield(perm, "dies")
        settle(game)
        return game, a

    def test_parse(self):
        (ability,) = triggered_abilities(OOZE)
        self.assertEqual((ability.event, ability.effects), ("dies", (ReturnWithCounter("-1/-1"),)))
        (ability,) = triggered_abilities(WOLF)
        self.assertEqual(ability.effects, (ReturnWithCounter("+1/+1"),))
        for card in (OOZE, WOLF):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_persist_returns_with_a_minus_counter(self):
        game, a = self.kill(OOZE)
        (back,) = a.battlefield
        self.assertEqual((back.card.name, back.counters, back.sick, a.graveyard), ("Ooze", {"-1/-1": 1}, True, []))
        self.assertEqual((game.power(back), game.toughness(back)), (1, 1))

    def test_it_does_not_return_a_second_time(self):
        game, a = self.kill(OOZE)
        back = a.battlefield[0]
        game._leave_battlefield(back, "dies")
        settle(game)
        self.assertEqual((a.battlefield, [c.name for c in a.graveyard]), ([], ["Ooze"]))

    def test_undying_returns_with_a_plus_counter(self):
        game, a = self.kill(WOLF)
        (back,) = a.battlefield
        self.assertEqual(back.counters, {"+1/+1": 1})
        self.assertEqual((game.power(back), game.toughness(back)), (3, 3))
        game._leave_battlefield(back, "dies")
        settle(game)
        self.assertEqual(a.battlefield, [])

    def test_only_the_matching_counter_stops_it(self):
        _, a = self.kill(OOZE, {"+1/+1": 1})
        self.assertEqual(len(a.battlefield), 1)
        _, a = self.kill(WOLF, {"-1/-1": 1})
        self.assertEqual(len(a.battlefield), 1)
        _, a = self.kill(OOZE, {"-1/-1": 1})
        self.assertEqual(a.battlefield, [])

    def test_a_token_does_not_come_back(self):
        _, a = self.kill(OOZE, token=True)
        self.assertEqual(a.battlefield, [])

    def test_exile_is_not_dying(self):
        game, _, _ = table()
        a = game.seats[0]
        perm = Permanent(OOZE)
        a.battlefield = [perm]
        game.exile(perm)
        settle(game)
        self.assertEqual(a.battlefield, [])

    def test_it_enters_again(self):
        card = creature("Healer", 2, 2, "Persist\nWhen this creature enters, you gain 1 life.")
        game, a = self.kill(card)
        self.assertEqual(a.life, 41)  # the enter trigger fired for the second entry

    def test_it_can_share_a_line_with_other_keywords(self):
        card = creature("Flyer", 2, 2, "Flying, persist")
        self.assertEqual(len(triggered_abilities(card)), 1)
        self.assertEqual(unsupported_lines(card), [])


if __name__ == "__main__":
    unittest.main()
