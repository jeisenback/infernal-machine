import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import attack_all, BEAR, BOLT, lands, run_stack, SPIRIT, table, table3, take_turn_attacking


def watcher(text, name="Watcher"):
    return Card(name=name, mana_cost="{1}", type_line="Creature — Wizard", oracle_text=text)


MAGECRAFT = watcher("Magecraft — Whenever you cast or copy an instant or sorcery spell, draw a card.")
BIG_CAST = watcher("Whenever you cast an instant or sorcery spell with mana value 5 or greater from your hand, draw a card.")
BIG_ANY = watcher("Whenever you cast an instant or sorcery spell with mana value 5 or greater, draw a card.")
PLAIN_CAST = watcher("Whenever you cast an instant or sorcery spell, draw a card.")
GROUP = watcher("Whenever one or more creatures you control deal combat damage to a player, draw a card.")
GROUP_TOKENS = watcher("Whenever one or more creature tokens you control deal combat damage to a player, draw a card.")
WRATH = Card(name="Big Wave", mana_cost="{3}{U}{U}", cmc=5.0, type_line="Sorcery", oracle_text="Draw a card.")


class ParseTests(unittest.TestCase):
    def test_watches(self):
        [m] = triggered_abilities(MAGECRAFT)
        self.assertEqual((m.event, m.watch.with_copy, m.watch.kind), ("cast", True, "instant or sorcery spell"))
        [b] = triggered_abilities(BIG_CAST)
        self.assertEqual((b.watch.mv_at_least, b.watch.from_hand), (5, True))
        [b] = triggered_abilities(BIG_ANY)
        self.assertEqual((b.watch.mv_at_least, b.watch.from_hand), (5, False))
        self.assertEqual(triggered_abilities(GROUP)[0].event, "creatures_combat_damage")
        self.assertEqual(triggered_abilities(GROUP_TOKENS)[0].event, "tokens_combat_damage")

    def test_the_report_understands_them(self):
        for card in (MAGECRAFT, BIG_CAST, BIG_ANY, GROUP, GROUP_TOKENS):
            self.assertEqual(unsupported_lines(card), [], card.name)


class CastTests(unittest.TestCase):
    def cast(self, game, seat, card, **kw):
        seat.cast_log.append((game.turn, card))
        game._observe("cast", card, seat, **kw)

    def test_magecraft_sees_casts_and_copies(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(MAGECRAFT)]
        self.cast(game, a, BOLT)
        run_stack(game)
        game._observe("copy", BOLT, a)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)

    def test_a_plain_cast_trigger_ignores_copies(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(PLAIN_CAST)]
        game._observe("copy", BOLT, a)
        run_stack(game)
        self.assertEqual(a.hand, [])

    def test_a_copy_made_by_another_player_does_not_count(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(MAGECRAFT)]
        game._observe("copy", BOLT, b)
        run_stack(game)
        self.assertEqual(a.hand, [])

    def test_mana_value_and_from_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 9
        a.battlefield = [Permanent(BIG_CAST)]
        for card, from_hand, expected in ((BOLT, True, 0), (WRATH, False, 0), (WRATH, True, 1)):
            self.cast(game, a, card, from_hand=from_hand)
            run_stack(game)
            self.assertEqual(len(a.hand), expected, (card.name, from_hand))

    def test_without_from_hand_any_zone_counts(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.battlefield = [Permanent(BIG_ANY)]
        self.cast(game, a, WRATH, from_hand=False)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_casting_from_hand_through_the_game_counts_as_from_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.hand = [WRATH]
        a.battlefield = [Permanent(BIG_CAST), *lands(5)]
        game._perform(a, CAST + "Big Wave")
        run_stack(game)
        self.assertEqual(len(a.hand), 2)  # Big Wave's own draw, and the watcher's


class GroupCombatDamageTests(unittest.TestCase):
    def test_once_for_several_creatures(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(GROUP), Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1 + 1)  # the draw step, then once for the three bears

    def test_once_per_player_hit(self):
        game, _ = table3(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(GROUP), Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1 + 1)  # the bear can only hit one player

    def test_token_version_needs_a_token(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(GROUP_TOKENS), Permanent(BEAR)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1)
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(GROUP_TOKENS), Permanent(BEAR), Permanent(SPIRIT)]
        a.library = [BEAR] * 5
        take_turn_attacking(game, a)
        self.assertEqual(len(a.hand), 1 + 1)


if __name__ == "__main__":
    unittest.main()
