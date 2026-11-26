"""Adapt N (CR 701.46a): "If this creature has no +1/+1 counters on it, put N +1/+1 counters on it.", from the cards' real Oracle
text. All seven cards whose only gap it was are fully playable. Trollbred Guardian (5/5, "{2}{G}: Adapt 2.") adapts to a 7/7 with
trample; adapting again puts no more counters; with a +1/+1 counter from elsewhere already on it, adapting does nothing. The counters
are checked as the ability resolves: two activations on the stack give two counters, not four. Etherium Pteramander's {6}{B} costs {1}
less for each other artifact: {3}{B} with three, not counting itself."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import RELIC, activate, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aeromunculus", "Etherium Pteramander", "Sauroform Hybrid", "Skatewing Spy", "Skitter Eel", "Temperamental Oozewagg",
         "Trollbred Guardian"]
GUARDIAN, PTERAMANDER = REAL["Trollbred Guardian"], REAL["Etherium Pteramander"]  # ("{6}{B}: Adapt 4. ... {1} less ... each other artifact")

# The guards these tests are there to catch (python tools/mutate.py tests.test_adapt).
MUTATIONS = [
    ("infernal_machine/effects/families/counters.py", 'game.on_battlefield(target) and not target.counters.get("+1/+1"):',
     "game.on_battlefield(target):", "only if it has no +1/+1 counters"),
    ("infernal_machine/effects/outcomes.py", '    (re.compile(r"adapt (\\d+)\\.", re.I), lambda m: Adapt(int(m[1]))),  # CR 701.46a\n', "",
     "the keyword action is read"),
    ("infernal_machine/game.py", '            kind = ability.discount_each.removeprefix("other ")', "            kind = ability.discount_each",
     "\"each other artifact\" counts artifacts"),
    ("infernal_machine/game.py", "if not (kind != ability.discount_each and p is permanent)))", "if True))", "not the source itself"),
]


def guardian(counters=0, mana=6):
    game, _ = table3()
    a = game.seats[0]
    permanent = Permanent(GUARDIAN, sick=False)
    if counters:
        permanent.counters["+1/+1"] = counters
    a.battlefield = [permanent] + lands(mana)
    return game, a, permanent


class AdaptTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_adapts_once(self):
        game, a, it = guardian()
        activate(game, a, "Adapt")
        self.assertEqual((it.counters.get("+1/+1"), game.power(it), game.has_keyword(it, "trample")), (2, 7, True))
        activate(game, a, "Adapt")
        self.assertEqual(it.counters.get("+1/+1"), 2)

    def test_a_counter_already_there_stops_it(self):
        game, a, it = guardian(counters=1)
        activate(game, a, "Adapt")
        self.assertEqual(it.counters.get("+1/+1"), 1)

    def test_it_is_checked_as_it_resolves(self):
        game, a, it = guardian()
        for _ in range(2):  # (both on the stack before either resolves)
            game._perform(a, next(x for x in game.legal_actions(a) if "Adapt" in x))
        run_stack(game)
        self.assertEqual(it.counters.get("+1/+1"), 2)


    def test_each_other_artifact_makes_it_cost_one_less(self):
        for others, mana, offered in ((3, 4, True), (3, 3, False), (0, 6, False)):  # ({3}{B}, not {2}{B}: it is an artifact too)
            game, _ = table3()
            a = game.seats[0]
            a.battlefield = [Permanent(PTERAMANDER, sick=False)] + [Permanent(RELIC) for _ in range(others)] + lands(mana)
            self.assertEqual(any("Adapt" in x for x in game.legal_actions(a)), offered, (others, mana))


if __name__ == "__main__":
    unittest.main()
