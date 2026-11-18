"""Issue #808: Amplify N, "(As this creature enters, put N +1/+1 counters on it for each card you reveal that shares a creature type with
it in your hand.)" (CR 702.38a), from the cards' real Oracle text. All seven cards whose only gap it was are fully playable. Kilnmouth
Dragon (Amplify 3) with two Dragon cards in hand: both revealed, six counters; one, three; a card of another type is never offered, and the
card itself does not count."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import AMPLIFY_DONE, AMPLIFY_PROMPT, Permanent
from tests.helpers import BEAR, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Aven Warhawk", "Canopy Crawler", "Daru Stinger", "Embalmed Brawler", "Glowering Rogon", "Kilnmouth Dragon", "Zombie Brute"]
DRAGON = REAL["Kilnmouth Dragon"]
WHELP = Card(name="Dragon Whelp", mana_cost="{2}{R}{R}", type_line="Creature — Dragon", power="2", toughness="3")
SECRET = Card(name="Secret Dragon", mana_cost="{3}{R}", type_line="Creature — Dragon", power="4", toughness="4")

# The guards these tests are there to catch (python tools/mutate.py tests.test_amplify).
MUTATIONS = [
    ("infernal_machine/game.py", "                counters[\"+1/+1\"] = counters.get(\"+1/+1\", 0) + n * shown",
     "                counters[\"+1/+1\"] = counters.get(\"+1/+1\", 0) + shown", "N counters for each card"),
    ("infernal_machine/game.py", '"card": sharing.pop(pick).name})', '"card": sharing.pop(0).name})', "the player's choice of which card"),
    ("infernal_machine/game.py", "and kinds & set(c.type_line.partition(\"\\u2014\")[2].split())]", "]", "only a card that shares a creature type"),
    ("infernal_machine/game.py", "sharing = [c for c in seat.hand if c is not permanent.card and (", "sharing = [c for c in seat.hand if (",
     "not the card itself"),
]


def reveal(count, only=None):
    """Reveal `count` cards, the first offered each time (or only those named `only`), then stop."""
    shown = []
    def policy(prompt, options):
        if not AMPLIFY_PROMPT.matches(prompt):
            return 0
        if len(shown) >= count:
            return options.index(AMPLIFY_DONE)
        pick = options.index(only) if only else 0
        shown.append(options[pick])
        return pick
    return policy


def enters(hand, count=2, only=None):
    game, players = table3(reveal(count, only))
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

    def test_the_player_chooses_which_cards(self):
        dragon, player = enters([SECRET, WHELP, BEAR], 1, only="Dragon Whelp")
        revealed = [e["card"] for e in player.events if e.get("event") == "revealed"]
        self.assertEqual((revealed, dragon.counters), (["Dragon Whelp"], {"+1/+1": 3}))  # (the Secret Dragon, first in hand, stays hidden)

    def test_only_cards_that_share_a_creature_type_and_not_itself(self):
        dragon, player = enters([WHELP, BEAR], 1)
        (offered, *_) = [options for prompt, options in player.prompts if AMPLIFY_PROMPT.matches(prompt)]
        self.assertEqual((offered, dragon.counters), (["Dragon Whelp", AMPLIFY_DONE], {"+1/+1": 3}))
        game, _ = table3(reveal(1))
        a = game.seats[0]
        dragon = Permanent(DRAGON)
        a.hand = [DRAGON]  # (the very card entering is not revealed for itself)
        game._enter(a, dragon)
        self.assertEqual(dragon.counters, {})


if __name__ == "__main__":
    unittest.main()
