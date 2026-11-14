"""The legend rule (CR 704.5j), from the cards' real Oracle text: a player who controls two or more legendary permanents with the same name
chooses one, and the rest are put into their owners' graveyards, indestructible or not (Avacyn, Angel of Hope). Each player is checked on
their own, different names don't clash, and Sakashima of a Thousand Faces turns it off for its controller."""

import unittest

from infernal_machine.game import LEGEND_PROMPT, Permanent
from tests.helpers import BEAR, activate, real, table3

AVACYN = real("Avacyn, Angel of Hope", "{5}{W}{W}{W}", "Legendary Creature — Angel", "Flying, vigilance, indestructible\nOther permanents you "
              "control have indestructible.", "8", "8", colors=("W",))
SAKASHIMA = real("Sakashima of a Thousand Faces", "{3}{U}", "Legendary Creature — Human Rogue", "You may have Sakashima enter as a copy of "
                 "another creature you control, except it has Sakashima's other abilities.\nThe \"legend rule\" doesn't apply to permanents "
                 "you control.\nPartner (You can have two commanders if both have partner.)", "3", "1", colors=("U",))
TOLSIMIR = real("Tolsimir Wolfblood", "{4}{G}{W}", "Legendary Creature — Elf Warrior", "Other green creatures you control get +1/+1.\nOther white "
                "creatures you control get +1/+1.\n{T}: Create Voja, a legendary 2/2 green and white Wolf creature token.", "3", "4",
                colors=("G", "W"))


def checked(policy=None, mine=(), theirs=()):
    game, _ = table3(policy) if policy else table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield, b.battlefield = list(mine), list(theirs)
    game._check_state()
    return game, a, b


class LegendRuleTests(unittest.TestCase):
    def test_the_chosen_one_stays_and_the_other_goes_even_if_indestructible(self):
        def keep_second(prompt, options):
            return 1 if LEGEND_PROMPT.matches(prompt) else 0
        first, second = Permanent(AVACYN), Permanent(AVACYN)
        game, a, _ = checked(keep_second, [first, second])
        self.assertEqual((a.battlefield, [c.name for c in a.graveyard]), ([second], ["Avacyn, Angel of Hope"]))

    def test_one_already_dying_is_not_counted(self):
        hurt, whole = Permanent(TOLSIMIR), Permanent(TOLSIMIR)
        hurt.damage = 6  # lethal (each Tolsimir makes the other 5/6): it dies, so the other one is the only Tolsimir left
        game, a, _ = checked(mine=[hurt, whole])
        self.assertEqual(a.battlefield, [whole])

    def test_each_player_is_checked_on_their_own(self):
        game, a, b = checked(mine=[Permanent(AVACYN)], theirs=[Permanent(AVACYN)])
        self.assertEqual((len(a.battlefield), len(b.battlefield)), (1, 1))

    def test_different_names_and_nonlegendary_ones_stay(self):
        game, a, _ = checked(mine=[Permanent(AVACYN), Permanent(TOLSIMIR), Permanent(BEAR), Permanent(BEAR)])
        self.assertEqual(len(a.battlefield), 4)

    def test_sakashima_turns_it_off_for_its_controller(self):
        game, a, _ = checked(mine=[Permanent(SAKASHIMA), Permanent(AVACYN), Permanent(AVACYN)])
        self.assertEqual(len(a.battlefield), 3)

    def test_a_second_named_legendary_token_replaces_the_first(self):
        game, _ = table3()
        a = game.seats[0]
        tolsimir = Permanent(TOLSIMIR)
        a.battlefield = [tolsimir]
        for _ in range(2):
            tolsimir.tapped = False
            activate(game, a, "Tolsimir")
            game._check_state()  # (the game checks them as a player would get priority: CR 704.3)
        self.assertEqual(sum(p.card.name == "Voja" for p in a.battlefield), 1)


if __name__ == "__main__":
    unittest.main()
