"""Copy a spell (#659): Jin-Gitaxias, Progress Tyrant ("an artifact, instant, or sorcery spell", copied or countered once each turn),
Kitsa, Otterball Elite ("Activate only if Kitsa's power is 3 or greater") and Storm of Saruman ("copy it, except the copy isn't
legendary")."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, BOLT, lands, pick, real, run_stack, table

JIN = real("Jin-Gitaxias, Progress Tyrant", "{5}{U}{U}", "Legendary Creature — Phyrexian Praetor",
           "Whenever you cast an artifact, instant, or sorcery spell, copy that spell. You may choose new targets for the copy. This ability "
           "triggers only once each turn. (A copy of a permanent spell becomes a token.)\nWhenever an opponent casts an artifact, instant, or "
           "sorcery spell, counter that spell. This ability triggers only once each turn.", "5", "5", colors=("U",))
KITSA = real("Kitsa, Otterball Elite", "{1}{U}", "Legendary Creature — Otter Wizard",
             "Vigilance\nProwess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)\n{T}: Draw a card, then "
             "discard a card.\n{2}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy. Activate "
             "only if Kitsa's power is 3 or greater.", "1", "3", colors=("U",))
SARUMAN = real("Storm of Saruman", "{4}{U}{U}", "Enchantment",
               "Ward {3}\nWhenever you cast your second spell each turn, copy it, except the copy isn't legendary. You may choose new targets "
               "for the copy. (A copy of a permanent spell becomes a token.)", colors=("U",))
TRINKET = real("Trinket", "{1}", "Artifact", "")
CROWN = real("Crown of Ages", "{1}", "Legendary Artifact", "")
STUDY = real("Quick Study", "{1}", "Sorcery", "Draw a card.")


def cast(game, seat, card):
    seat.hand.append(card)
    game._perform(seat, f"Cast: {card.name}")
    run_stack(game)


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class JinGitaxiasTests(unittest.TestCase):
    def board(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(JIN, sick=False)] + lands(6)
        mine.library = [BEAR] * 10
        return game, mine, theirs

    def test_an_artifact_spell_is_copied_as_a_token(self):
        game, mine, theirs = self.board()
        cast(game, mine, TRINKET)
        trinkets = [p for p in mine.battlefield if p.card.name == "Trinket"]
        self.assertEqual(len(trinkets), 2)
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in trinkets), 1)

    def test_only_the_first_spell_each_turn_is_copied(self):
        game, mine, theirs = self.board()
        cast(game, mine, STUDY)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 3)  # 2 + 1: the first one was copied

    def test_a_creature_spell_is_not_copied(self):
        game, mine, theirs = self.board()
        cast(game, mine, BEAR)
        self.assertEqual(names(mine).count("Bear"), 1)

    def test_an_opponents_first_spell_each_turn_is_countered(self):
        game, mine, theirs = self.board()
        game.active = 1
        theirs.battlefield, theirs.library = lands(2), [BEAR] * 5
        cast(game, theirs, BOLT)
        self.assertEqual(theirs.hand, [])  # countered: no card drawn
        cast(game, theirs, BOLT)
        self.assertEqual(len(theirs.hand), 1)


class KitsaTests(unittest.TestCase):
    def offered(self, power_counters):
        game, _, _ = table(pick("Spell:"))
        mine = game.seats[0]
        kitsa = Permanent(KITSA, sick=False)
        kitsa.counters["+1/+1"] = power_counters
        mine.battlefield, mine.library = [kitsa] + lands(4), [BEAR] * 10
        mine.hand = [STUDY]
        game._perform(mine, "Cast: Quick Study")  # (it stays on the stack: Prowess makes Kitsa 1 bigger)
        game._put_triggers_on_stack()
        while len(game.stack) > 1:
            game._resolve(game.stack.pop())
        return game, mine, [a for a in game.legal_actions(mine) if "Copy target" in a]

    def test_at_power_3_the_spell_can_be_copied(self):
        game, mine, actions = self.offered(1)  # 1 + 1 counter + 1 from Prowess
        self.assertEqual(len(actions), 1)
        game._perform(mine, actions[0])
        run_stack(game)
        self.assertEqual(len(mine.hand), 2)

    def test_below_power_3_it_cannot(self):
        self.assertEqual(self.offered(0)[2], [])


class StormOfSarumanTests(unittest.TestCase):
    def board(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(SARUMAN)] + lands(4), [BEAR] * 10
        return game, mine

    def test_the_second_spell_is_copied_and_a_legendary_copy_is_not_legendary(self):
        game, mine = self.board()
        cast(game, mine, TRINKET)
        cast(game, mine, CROWN)
        crowns = [p for p in mine.battlefield if p.card.name == "Crown of Ages"]
        self.assertEqual(len(crowns), 2)  # (two legendary permanents of one name would leave one)
        copy = next(p for p in crowns if p.card.type_line.startswith("Token"))
        self.assertNotIn("Legendary", copy.card.type_line)

    def test_the_first_spell_is_not_copied(self):
        game, mine = self.board()
        cast(game, mine, CROWN)
        self.assertEqual(names(mine).count("Crown of Ages"), 1)


if __name__ == "__main__":
    unittest.main()
