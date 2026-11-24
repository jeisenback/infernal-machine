"""Issue #851: For Mirrodin!, "(When this Equipment enters, create a 2/2 red Rebel creature token, then attach this to it.)"
(CR 702.163a), from the cards' real Oracle text. All seven cards whose only gap it was are fully playable. Vulshok Splitter ({3}{R},
"Equipped creature gets +2/+0.") cast with four lands makes a 2/2 red Rebel token wearing it, a 4/2; equipped to another creature
afterwards it makes no other token; an Equipment without For Mirrodin! makes none."""

import unittest

from infernal_machine.game import CAST, Permanent
from tests.helpers import BEAR, lands, real, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Kemba's Banner", "Dragonwing Glider", "Barbed Batterfist", "Mirran Bardiche", "Vulshok Splitter", "Goldwarden's Helm",
         "Sylvok Battle-Chair"]
SPLITTER = REAL["Vulshok Splitter"]
PLAIN = real("Plain Fist", "{1}{R}", "Artifact — Equipment", "Equipped creature gets +1/-1.\nEquip {1}")  # (no For Mirrodin!)

# The guards these tests are there to catch (python tools/mutate.py tests.test_for_mirrodin).
MUTATIONS = [
    ("infernal_machine/effects/families/combat_and_pump.py", "HERO if self.hero else REBEL if self.rebel else None",
     "HERO if self.hero else None", "a Rebel, not a Germ"),
    ("infernal_machine/effects/triggers.py", '        if "for mirrodin!" in words:', '        if False:', "the keyword makes the token"),
]


def cast(card):
    """Seat 0, with four lands and a Bear, casts `card`."""
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield = [card], lands(4) + [Permanent(BEAR)]
    game._perform(a, CAST + card.name)
    run_stack(game)
    (equipment,) = [p for p in a.battlefield if p.card is card]
    return game, a, equipment


def tokens(seat):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token")]


class ForMirrodinTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_makes_a_red_rebel_wearing_it(self):
        game, a, splitter = cast(SPLITTER)
        (rebel,) = tokens(a)
        self.assertEqual((rebel.card.name, rebel.card.colors, splitter.attached_to), ("Rebel", ("R",), rebel))
        self.assertEqual((game.power(rebel), game.toughness(rebel)), (4, 2))

    def test_moving_it_makes_no_other_token(self):
        game, a, splitter = cast(SPLITTER)
        (bear,) = [p for p in a.battlefield if p.card is BEAR]
        game.attach(splitter, bear)
        run_stack(game)
        self.assertEqual((len(tokens(a)), game.power(bear)), (1, 4))

    def test_an_equipment_without_it_makes_none(self):
        _, a, fist = cast(PLAIN)
        self.assertEqual((tokens(a), fist.attached_to), ([], None))


if __name__ == "__main__":
    unittest.main()
