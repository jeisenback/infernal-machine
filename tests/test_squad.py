"""Issue #837: Squad {cost}, "(As an additional cost to cast this spell, you may pay {cost} any number of times. When this creature
enters, create that many tokens that are copies of it.)" (CR 702.157a), from the cards' real Oracle text. All eleven cards whose only gap
it was are fully playable. Galadhrim Brigade ({2}{G}, Squad {1}{G}): with seven lands its caster may pay squad twice for two token copies;
paid none, no token; a token copy (not cast, so not kicked) makes no more."""

import unittest

from infernal_machine.game import CAST, MULTIKICKER_PROMPT
from tests.helpers import lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Galadhrim Brigade", "Imperial Hullbreachers", "Powder Ganger", "Roadkill Rodney", "Securitron Squadron", "Sicarian Infiltrator",
         "Space Marine Devastator", "Ultramarines Honour Guard", "Vanguard Suppressor", "Wasteland Raider", "Zephyrim"]
BRIGADE = REAL["Galadhrim Brigade"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_squad).
MUTATIONS = [
    ("infernal_machine/effects/costs.py", "or _OFFSPRING.fullmatch(line) or _SQUAD.fullmatch(line):", "or _OFFSPRING.fullmatch(line):",
     "the squad cost is paid like a kicker"),
    ("infernal_machine/effects/costs.py", 'and _KICKER.fullmatch(line) or _SQUAD.fullmatch(line) for line', "and _KICKER.fullmatch(line) for line",
     "any number of times"),
    ("infernal_machine/effects/families/copying.py", "count = target.kicked if self.per_kick else game.amount(self.count)",
     "count = game.amount(self.count)", "one token for each time"),
    ("infernal_machine/effects/triggers.py", '(CopySelfToken(per_kick=True),), False, line, condition=Condition("kicked")))',
     "(CopySelfToken(per_kick=True),), False, line))", "only if it was paid"),
]


def times(n):
    return lambda prompt, options: options.index(str(n)) if MULTIKICKER_PROMPT.matches(prompt) else 0


def cast(n, mana=7, queued=None):
    """Seat 0, with `mana` lands, casts Galadhrim Brigade paying squad `n` times (the texts of the triggers queued go to `queued`)."""
    game, players = table3(times(n))
    if queued is not None:
        original = game._queue

        def recording(ability, *args, **kwargs):
            before = len(game.pending)
            original(ability, *args, **kwargs)
            if len(game.pending) > before:
                queued.append(ability.text)
        game._queue = recording
    a = game.seats[0]
    a.hand, a.battlefield = [BRIGADE], lands(mana)
    game._perform(a, CAST + BRIGADE.name)
    run_stack(game)
    brigades = [p for p in a.battlefield if p.card.name == BRIGADE.name]
    return players, brigades


class SquadTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_token_copy_for_each_time_it_was_paid(self):
        players, brigades = cast(2)
        self.assertEqual(sorted(p.card.type_line.startswith("Token") for p in brigades), [False, True, True])
        (asked,) = [options for prompt, options in players[0].prompts if MULTIKICKER_PROMPT.matches(prompt)]
        self.assertEqual(asked, ["0", "1", "2"])  # (seven lands: {2}{G} and twice {1}{G})

    def test_paid_none_no_token(self):
        queued = []
        _, brigades = cast(0, queued=queued)
        self.assertEqual((len(brigades), [t for t in queued if t.startswith("Squad")]), (1, []))  # (no trigger either)
        _, brigades = cast(0, mana=3)
        self.assertEqual(len(brigades), 1)

    def test_the_tokens_make_no_more(self):
        _, brigades = cast(1)
        self.assertEqual(len(brigades), 2)


if __name__ == "__main__":
    unittest.main()
