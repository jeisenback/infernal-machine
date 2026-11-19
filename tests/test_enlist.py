"""Issue #838: Enlist, "(As this creature attacks, you may tap a nonattacking creature you control without summoning sickness. When you
do, add its power to this creature's until end of turn.)" (CR 702.154a), from the cards' real Oracle text. All nine cards whose only gap
it was are fully playable. Linebreaker Baloth (4/5) attacks and enlists a Bear (2/2): the Bear is tapped and the Baloth is 6/5 until end
of turn; declined, nothing changes; a creature with summoning sickness, or one attacking too (with vigilance, so untapped), is not
offered; an attacker without enlist is not asked."""

import unittest

from infernal_machine.combat import ATTACK_PROMPT, ENLIST_PROMPT, NO_ENLIST
from infernal_machine.game import Permanent
from tests.helpers import BEAR, real, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Argivian Cavalier", "Balduvian Berserker", "Barkweave Crusher", "Benalish Faithbonder", "Coalition Skyknight", "Coalition Warbrute",
         "Hexbane Tortoise", "Linebreaker Baloth", "Yavimaya Steelcrusher"]
BALOTH = REAL["Linebreaker Baloth"]
KNIGHT = real("Vigilant Knight", "{2}{W}", "Creature — Human Knight", "Vigilance", "3", "3")  # (attacks and stays untapped)

# The guards these tests are there to catch (python tools/mutate.py tests.test_enlist).
MUTATIONS = [
    ("infernal_machine/combat.py", "        self.game.modify_until_end_of_turn(attacker, Modifier(max(0, self.game.power(enlisted)), 0))",
     "        pass", "it adds the creature's power"),
    ("infernal_machine/combat.py", "        self.game.tap(enlisted)\n", "", "the enlisted creature is tapped"),
    ("infernal_machine/combat.py", "and not any(a.attacker is p for a in self.attacks) and not self.game.summoning_sick(seat, p)]",
     "and not any(a.attacker is p for a in self.attacks)]", "not one with summoning sickness"),
    ("infernal_machine/combat.py", "and not any(a.attacker is p for a in self.attacks) and not self.game.summoning_sick(seat, p)]",
     "and not self.game.summoning_sick(seat, p)]", "not one that attacks"),
    ("infernal_machine/combat.py", '        if not self.game.has_keyword(attacker, "enlist"):\n            return\n', "", "only a creature with enlist"),
]


def policy(attackers, enlist):
    """Attack with the creatures named in `attackers`; enlist the one named `enlist` (None: don't)."""
    def choose(prompt, options):
        if ATTACK_PROMPT.matches(prompt):
            return 1 if any(f"{name} " in prompt for name in attackers) else 0
        if ENLIST_PROMPT.matches(prompt):
            return next((i for i, o in enumerate(options) if enlist and o.startswith(enlist + " ")), 0)
        return 0
    return choose


def attack(attackers=("Linebreaker Baloth",), enlist="Bear", sick_bear=False):
    """Seat 0 has Linebreaker Baloth, a Bear and a vigilant Knight; it attacks with `attackers` and enlists `enlist`."""
    game, players = table3(policy(attackers, enlist))
    a = game.seats[0]
    baloth, bear, ogre = Permanent(BALOTH, sick=False), Permanent(BEAR, sick=sick_bear), Permanent(KNIGHT, sick=False)
    a.battlefield = [baloth, bear, ogre]
    game.combat.declare_attackers(a)
    return game, players, baloth, bear, ogre


def enlist_options(players):
    return [options for prompt, options in players[0].prompts if ENLIST_PROMPT.matches(prompt)]


class EnlistTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_it_taps_the_creature_and_adds_its_power(self):
        game, _, baloth, bear, _ = attack()
        self.assertEqual((game.power(baloth), game.toughness(baloth), bear.tapped), (6, 5, True))

    def test_declined_nothing_changes(self):
        game, _, baloth, bear, _ = attack(enlist=None)
        self.assertEqual((game.power(baloth), bear.tapped), (4, False))

    def test_not_a_sick_creature_nor_an_attacking_one(self):
        _, players, _, _, _ = attack(attackers=("Linebreaker Baloth", "Vigilant Knight"), sick_bear=True)
        self.assertEqual(enlist_options(players), [])  # (the Bear is sick, the Knight attacks, untapped)

    def test_an_attacker_without_enlist_is_not_asked(self):
        _, players, _, bear, _ = attack(attackers=("Vigilant Knight",))
        self.assertEqual((enlist_options(players), bear.tapped), ([], False))


if __name__ == "__main__":
    unittest.main()
