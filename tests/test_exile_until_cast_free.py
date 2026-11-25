"""Casting the first nonland card exiled or revealed from the top of the library without paying its mana cost, from the cards' real
Oracle text. All four cards are fully playable. Nico Minoru, Runaway ("{2}{R}, {T}, Discard a card: Exile cards from the top of your
library until you exile a nonland card. You may cast that card without paying its mana cost."): over two lands to a Bear, the Bear is
cast (from exile, so Nico deals 2 damage to each opponent) and the lands stay exiled; declined, the Bear stays exiled too, not in the
hand, and nothing goes back to the library. Treasure Keeper ("reveal ... until you reveal a nonland card with mana value 3 or less ...
Put all revealed cards not cast this way on the bottom"): a five-drop is passed, the Bear is cast, the rest go to the bottom."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CASCADE_PROMPT, Permanent
from tests.helpers import BEAR, BIG, FOREST, activate, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Nico Minoru, Runaway", "Wanda's Vision", "Q, Your Illustrious Host", "Treasure Keeper"]
NICO, KEEPER = REAL["Nico Minoru, Runaway"], REAL["Treasure Keeper"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_exile_until_cast_free).
MUTATIONS = [
    ("infernal_machine/game.py", "        if take and any(c is found for c in seat.exile):", "        if any(c is found for c in seat.exile):",
     "declined, it stays exiled"),
    ("infernal_machine/effects/outcomes.py", "random order\\.\", re.I), lambda m: Cascade(int(m[1]) + 1)),",
     "random order\\.\", re.I), lambda m: Cascade(int(m[1]))),", "mana value 3 or less, not less than 3"),
]


def decline(prompt, options):
    return 1 if CASCADE_PROMPT.matches(prompt) else 0


class ExileUntilCastFreeTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def nico(self, *policies):
        game, _ = table3(*policies)
        a, b, _ = game.seats
        a.battlefield = lands(3) + [Permanent(NICO, sick=False)]
        a.hand, a.library = [FOREST], [FOREST, FOREST, BEAR, BIG]
        activate(game, a, "Exile cards")
        return game, a, b

    def test_the_first_nonland_card_is_cast_and_the_lands_stay_exiled(self):
        game, a, b = self.nico()
        self.assertEqual(([p.card.name for p in a.battlefield if p.card is BEAR], [c.name for c in a.exile]),
                         (["Bear"], ["Forest", "Forest"]))
        self.assertEqual((a.library, b.life), ([BIG], 38))  # (cast from exile: Nico's own trigger)

    def test_declined_it_stays_exiled(self):
        game, a, _ = self.nico(decline)
        self.assertEqual((sorted(c.name for c in a.exile), BEAR in a.hand, a.library), (["Bear", "Forest", "Forest"], False, [BIG]))

    def test_a_revealed_card_with_mana_value_3_or_less_is_cast_and_the_rest_go_to_the_bottom(self):
        game, _ = table3()
        a = game.seats[0]
        keeper = Permanent(KEEPER)
        three = Card(name="Trio", mana_cost="{3}", cmc=3.0, type_line="Artifact")
        a.battlefield, a.library = [keeper], [BIG, FOREST, three, BEAR]
        game.destroy(keeper)
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], a.library[0], sorted(c.name for c in a.library[1:])),
                         (["Trio"], BEAR, ["Big", "Forest"]))


if __name__ == "__main__":
    unittest.main()
