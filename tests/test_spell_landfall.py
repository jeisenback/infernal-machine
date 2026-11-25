"""Landfall on an instant: "Landfall — If you had a land enter the battlefield under your control this turn, ... instead." (the
condition `land_entered`), from the cards' real Oracle text. All four cards are fully playable. Cast after its caster played a land
this turn, Groundswell makes the Bear 6/6, Tomb Hex gives the Ogre -4/-4, Mysteries of the Deep draws three and Rest for the Weary
gains 8 life; without a land, +2/+2, -2/-2, two cards and 4 life. Another player's land this turn does not count. Four more cards
read "If <a condition the engine knows>, that creature gets ... until end of turn instead." the same way (For the Family, ...)."""

import unittest

from infernal_machine.game import CAST, PLAY_LAND, Permanent
from tests.helpers import BEAR, FOREST, OGRE, choose, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Groundswell", "Tomb Hex", "Mysteries of the Deep", "Rest for the Weary"]
SAME_SENTENCE = ["For the Family", "Might of Old Krosa", "Olivia's Midnight Ambush", "Tragic Banshee"]  # ("If <condition>, that creature gets ... instead.")

# The guards these tests are there to catch (python tools/mutate.py tests.test_spell_landfall).
MUTATIONS = [
    ("infernal_machine/effects/outcomes.py", "a land entered the battlefield under your control this turn|you had a land enter the battlefield",
     "a land entered the battlefield under your control this turn|you had a land enter the stack", "the condition is read"),
    ("infernal_machine/effects/families/life_and_damage.py", "game.change_life(target, self.instead if more else game.amount(self.amount))",
     "game.change_life(target, game.amount(self.amount))", "8 life after a land"),
    ("infernal_machine/effects/outcomes.py", 'fits=lambda previous, marker: previous.instead_if is None),\n    Follow(_InsteadCountersOnSource',
     'fits=lambda previous, marker: False),\n    Follow(_InsteadCountersOnSource', "the life sentence folds into the gain"),
]


def cast(name, land=True, theirs_land=False):
    """Seat 0, with five lands and a Bear, plays a Forest first if `land` (seat 1 has one enter if `theirs_land`), then casts `name`,
    aimed at its Bear or at seat 1's Ogre."""
    game, players = table3()
    a, b, _ = game.seats
    bear, ogre = Permanent(BEAR, sick=False), Permanent(OGRE)
    a.battlefield, a.hand, a.library = lands(5) + [bear], [REAL[name], FOREST], [BEAR] * 5
    b.battlefield = [ogre]
    players[0].policy = choose(game, ogre if name == "Tomb Hex" else bear, a)
    if land:
        game._perform(a, PLAY_LAND + "Forest")
        run_stack(game)
    if theirs_land:
        game._enter(b, Permanent(FOREST))
    game._perform(a, CAST + name)
    run_stack(game)
    return game, a, bear, ogre


class SpellLandfallTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)
        wording_unlocked(self, SAME_SENTENCE)

    def test_after_a_land_it_does_more(self):
        game, _, bear, _ = cast("Groundswell")
        self.assertEqual((game.power(bear), game.toughness(bear)), (6, 6))
        game, _, _, ogre = cast("Tomb Hex")
        game._check_state()  # (a 3/3 with -4/-4)
        self.assertEqual([c.name for c in game.seats[1].graveyard], ["Ogre"])
        _, a, _, _ = cast("Mysteries of the Deep")
        self.assertEqual(len(a.hand), 3)
        _, a, _, _ = cast("Rest for the Weary")
        self.assertEqual(a.life, 48)

    def test_without_a_land_it_does_the_first(self):
        game, _, bear, _ = cast("Groundswell", land=False)
        self.assertEqual(game.power(bear), 4)
        game, _, _, ogre = cast("Tomb Hex", land=False)
        game._check_state()
        self.assertEqual((ogre in game.seats[1].battlefield, game.toughness(ogre)), (True, 1))
        _, a, _, _ = cast("Mysteries of the Deep", land=False)
        self.assertEqual(len(a.hand), 3)  # (the Forest still in hand, and two cards)
        _, a, _, _ = cast("Rest for the Weary", land=False)
        self.assertEqual(a.life, 44)

    def test_another_players_land_does_not_count(self):
        game, _, bear, _ = cast("Groundswell", land=False, theirs_land=True)
        self.assertEqual(game.power(bear), 4)


if __name__ == "__main__":
    unittest.main()
