"""Issue #808: Amplify N, "(As this creature enters, put N +1/+1 counters on it for each card you reveal that shares a creature type with
it in your hand.)" (CR 702.38a), from the cards' real Oracle text. All seven cards whose only gap it was are fully playable. Kilnmouth
Dragon (Amplify 3) with two Dragon cards in hand: both revealed, six counters; one, three; a card of another type is never offered, and the
card itself does not count."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import AMPLIFY_PROMPT, Permanent
from tests.helpers import BEAR, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aven Warhawk", "Canopy Crawler", "Daru Stinger", "Embalmed Brawler", "Glowering Rogon", "Kilnmouth Dragon", "Zombie Brute"]
DRAGON = REAL["Kilnmouth Dragon"]
WHELP = Card(name="Dragon Whelp", mana_cost="{2}{R}{R}", type_line="Creature — Dragon", power="2", toughness="3")

# The guards these tests are there to catch (python tools/mutate.py tests.test_amplify).
MUTATIONS = [
    ("infernal_machine/game.py", "                    counters[\"+1/+1\"] = counters.get(\"+1/+1\", 0) + n * shown",
     "                    counters[\"+1/+1\"] = counters.get(\"+1/+1\", 0) + shown", "N counters for each card"),
    ("infernal_machine/game.py", "and kinds & set(c.type_line.partition(\"\\u2014\")[2].split())]", "]", "only a card that shares a creature type"),
    ("infernal_machine/game.py", "sharing = [c for c in seat.hand if c is not permanent.card and (", "sharing = [c for c in seat.hand if (",
     "not the card itself"),
]


def reveal(count):
    return lambda prompt, options: options.index(str(count)) if AMPLIFY_PROMPT.matches(prompt) else 0


def enters(hand, count=2):
    game, players = table3(reveal(count))
    a = game.seats[0]
    dragon = Permanent(DRAGON)
    a.hand = list(hand)
    game._enter(a, dragon)
    return dragon, players[0]


class AmplifyTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_n_counters_for_each_card_revealed(self):
        for count, counters in ((2, {"+1/+1": 6}), (1, {"+1/+1": 3}), (0, {})):
            dragon, _ = enters([WHELP, WHELP, BEAR], count)
            self.assertEqual(dragon.counters, counters, count)

    def test_only_cards_that_share_a_creature_type_and_not_itself(self):
        dragon, player = enters([WHELP, BEAR], 1)
        (offered,) = [options for prompt, options in player.prompts if AMPLIFY_PROMPT.matches(prompt)]
        self.assertEqual((offered, dragon.counters), (["1", "0"], {"+1/+1": 3}))
        game, _ = table3(reveal(1))
        a = game.seats[0]
        dragon = Permanent(DRAGON)
        a.hand = [DRAGON]  # (the very card entering is not revealed for itself)
        game._enter(a, dragon)
        self.assertEqual(dragon.counters, {})


if __name__ == "__main__":
    unittest.main()
