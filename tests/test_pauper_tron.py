"""Pauper Tron's missing cards (#646), from their real Oracle text: Bonder's Ornament (each player who controls one draws), Mystical
Teachings (an instant or a card with flash), Prohibit (a mana-value cap that kicker raises), Stream of Thought (shuffle up to four cards
back), Tangle (attacking creatures skip their next untap) and Ethereal Haze (prevent all damage creatures would deal this turn)."""

import unittest
from dataclasses import replace

from infernal_machine.game import ACTIVATE, CAST, DONE, KICKER_PROMPT, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, FOREST, lands, pick, real, run_stack, script, table3

ORNAMENT = real("Bonder's Ornament", "{3}", "Artifact", "{T}: Add one mana of any color.\n{4}, {T}: Each player who controls a permanent named "
                "Bonder's Ornament draws a card.")
TEACHINGS = real("Mystical Teachings", "{3}{U}", "Instant", "Search your library for an instant card or a card with flash, reveal it, put it "
                 "into your hand, then shuffle.\nFlashback {5}{B} (You may cast this card from your graveyard for its flashback cost. Then "
                 "exile it.)", colors=("U",))
PROHIBIT = real("Prohibit", "{1}{U}", "Instant", "Kicker {2} (You may pay an additional {2} as you cast this spell.)\nCounter target spell if "
                "its mana value is 2 or less. If this spell was kicked, counter that spell if its mana value is 4 or less instead.", colors=("U",))
STREAM = real("Stream of Thought", "{U}", "Sorcery", "Target player mills four cards. You shuffle up to four cards from your graveyard into "
              "your library.\nReplicate {2}{U}{U} (When you cast this spell, copy it for each time you paid its replicate cost. You may choose "
              "new targets for the copies.)", colors=("U",))
TANGLE = real("Tangle", "{1}{G}", "Instant", "Prevent all combat damage that would be dealt this turn.\nEach attacking creature doesn't untap "
              "during its controller's next untap step.", colors=("G",))
HAZE = real("Ethereal Haze", "{W}", "Instant — Arcane", "Prevent all damage that would be dealt by creatures this turn.", colors=("W",))
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
FLASHER = real("Flash Bear", "{1}{G}", "Creature — Bear", "Flash", "2", "2", colors=("G",))
THREE = real("Three Drop", "{2}{U}", "Sorcery", "Draw a card.", colors=("U",))


class PauperTronTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ORNAMENT, TEACHINGS, PROHIBIT, STREAM, TANGLE, HAZE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_bonders_ornament_draws_for_each_player_who_controls_one(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = lands(4) + [Permanent(ORNAMENT)]
        b.battlefield = [Permanent(ORNAMENT)]
        for seat in game.seats:
            seat.library = [FOREST] * 3
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Bonder's Ornament") and "{4}" in x))
        run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand), len(c.hand)), (1, 1, 0))

    def test_mystical_teachings_finds_an_instant_or_a_card_with_flash_only(self):
        asked = []
        policy = pick("Flash Bear")
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or policy(prompt, options))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(4), [TEACHINGS], [BEAR, SHOCK, FLASHER, THREE]
        game._perform(a, CAST + "Mystical Teachings")
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Flash Bear"])
        self.assertEqual(sorted(o for options in asked for o in options if o != DONE), ["Flash Bear", "Shock"])

    def test_prohibit_counters_mana_value_two_or_four_when_kicked(self):
        for kick, countered in (("No", False), ("Yes", True)):
            game, _ = table3(lambda prompt, options, kick=kick: options.index(kick) if KICKER_PROMPT.matches(prompt) else 0)
            a, b, _ = game.seats
            a.battlefield, a.hand = lands(4), [PROHIBIT]
            game.stack.append(StackItem(THREE, b))
            game._perform(a, CAST + "Prohibit")
            game._resolve(game.stack.pop())
            self.assertEqual(any(i.card is THREE for i in game.stack), not countered, kick)

    def test_stream_of_thought_mills_then_shuffles_back_up_to_four_chosen(self):
        game, _ = table3(script("Player: B", "Bear", "Bear", DONE))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.graveyard, a.library = lands(1), [STREAM], [BEAR, replace(BEAR), BIG], [FOREST] * 2
        b.library = [FOREST] * 6
        game._perform(a, CAST + "Stream of Thought")
        run_stack(game)
        self.assertEqual((len(b.library), len(b.graveyard)), (2, 4))
        self.assertEqual((sorted(c.name for c in a.graveyard), sorted(c.name for c in a.library)),
                         (["Big", "Stream of Thought"], ["Bear", "Bear", "Forest", "Forest"]))

    def test_tangle_keeps_attackers_tapped_through_their_next_untap(self):
        game, _ = table3()
        a, b, _ = game.seats
        attacker, home = Permanent(BEAR, tapped=True), Permanent(BEAR, tapped=True)
        b.battlefield = [attacker, home]
        game.combat.add_attacker(attacker, b, a)
        a.battlefield, a.hand = lands(2), [TANGLE]
        game._perform(a, CAST + "Tangle")
        run_stack(game)
        game.step = "untap"
        game._turn_based_actions(b)
        self.assertEqual((attacker.tapped, home.tapped), (True, False))

    def test_ethereal_haze_prevents_damage_from_creatures_only(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        a.battlefield, a.hand = lands(1), [HAZE]
        game._perform(a, CAST + "Ethereal Haze")
        run_stack(game)
        life = a.life
        game.damage(a, 2, bear)
        self.assertEqual(a.life, life)
        game.damage(a, 2, Permanent(SHOCK))
        self.assertEqual(a.life, life - 2)


if __name__ == "__main__":
    unittest.main()
