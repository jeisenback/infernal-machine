"""Two pieces of the most played staples, from the cards' real Oracle text. "protection from each color" is a protection keyword
(CR 702.16j: from each color in turn), so Akroma's Will's second mode makes the Bear protected from a red source and not from a
colorless one, and Iridescent Angel and Eldritch Immunity read too. "You and permanents you control gain hexproof until end of turn."
(Lazotep Plating) gives the player hexproof for the turn as well (`HexproofThisTurn`, read by `Game._player_untargetable`): an
opponent can't target them, they still can, and on the next turn it is gone. "Permanents you control gain ..." gave nothing before
(it was read as a creature type, "Permanent"): Heroic Intervention now gives the Bear hexproof and indestructible. Dawn's Truce with
the gift promised gives its permanents indestructible "also"; without it, not. All seven cards whose only gap these were are fully
playable."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, gift_table, lands, run_stack, script, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Akroma's Will", "Dawn's Truce", "Etched Champion", "Iridescent Angel", "Lazotep Plating", "Pristine Angel"]  # (and Eldritch
# Immunity, playable too, though its {C} is mana the smoke table doesn't have)
WILL, PLATING, TRUCE = REAL["Akroma's Will"], REAL["Lazotep Plating"], REAL["Dawn's Truce"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_protection_each_color).
MUTATIONS = [
    ("infernal_machine/effects/common.py", '    if what in ("all colors", "each color"):', '    if what in ("all colors",):',
     "from each color: every color"),
    ("infernal_machine/game.py", "(seat.hexproof_turn == self.turn and caster is not seat)", "(seat.hexproof_turn == self.turn)",
     "only an opponent's"),
    ("infernal_machine/game.py", "(seat.hexproof_turn == self.turn and caster is not seat)", "(seat.hexproof_turn >= 0 and caster is not seat)",
     "until end of turn"),
    ("infernal_machine/effects/outcomes.py", '    if not effects and " also " in sentence:', '    if False:', "the kicked sentence with \"also\""),
    ("infernal_machine/effects/outcomes.py", 'lambda m: PumpEach(_modifier(m, 2), permanents=True) if m[1] == "Permanent" else',
     'lambda m: PumpEach(_modifier(m, 2), subtype=m[1]) if m[1] == "Permanent" else', "every permanent, not a creature type"),
]


def players(game, caster):
    return [t for _, t in game.target_options("player", caster) if t in game.seats]


class ProtectionEachColorTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_akromas_will_gives_protection_from_each_color(self):
        game, _ = table3(script("Creatures you control gain lifelink"))
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = [bear] + lands(4), [WILL]
        game._perform(a, CAST + WILL.name)
        run_stack(game)
        self.assertEqual((game.protected_from(bear, frozenset("R")), game.protected_from(bear, frozenset({"artifact"})),
                          game.has_keyword(bear, "indestructible")), (True, False, True))

    def test_you_gain_hexproof_until_end_of_turn(self):
        game, _ = table3()
        a, b, c = game.seats
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = [bear] + lands(2), [PLATING]
        game._perform(a, CAST + PLATING.name)
        run_stack(game)
        self.assertEqual((players(game, b), players(game, a), game.has_keyword(bear, "hexproof")), ([b, c], [a, b, c], True))
        game.turn += 1
        self.assertEqual(players(game, b), [a, b, c])

    def test_permanents_you_control_gain(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR, sick=False)
        a.battlefield, a.hand = [bear] + lands(2), [REAL["Heroic Intervention"]]
        game._perform(a, CAST + "Heroic Intervention")
        run_stack(game)
        self.assertEqual((game.has_keyword(bear, "hexproof"), game.has_keyword(bear, "indestructible")), (True, True))

    def test_the_promised_gift_also_gives_indestructible(self):
        for policy, expected in ((script("Give"), True), (None, False)):
            game, a, _, _ = gift_table(TRUCE, policy=policy or (lambda prompt, options: 0))
            bear = Permanent(BEAR, sick=False)
            a.battlefield.append(bear)
            game._perform(a, CAST + TRUCE.name)
            run_stack(game)
            self.assertEqual((game.has_keyword(bear, "hexproof"), game.has_keyword(bear, "indestructible")), (True, expected))


if __name__ == "__main__":
    unittest.main()
