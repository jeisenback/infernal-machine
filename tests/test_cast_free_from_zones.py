"""Casting without paying the mana cost from a graveyard, a hand or a library (#655), from the cards' real Oracle text: Torrential
Gearhulk and Goblin Dark-Dwellers (a target card in your graveyard, exiled after), Sword of Once and Future (a spell from your graveyard
with mana value 2 or less, exiled after), Silent-Blade Oni (a spell from the hand of the player it hit) and Villainous Wealth (any number
of spells with mana value X or less from the top X cards of the target opponent's library)."""

import unittest

from infernal_machine.game import CAST, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, FOREST, enter, lands, pick, real, run_stack, table3

GEARHULK = real("Torrential Gearhulk", "{4}{U}{U}", "Artifact Creature — Construct", "Flash\nWhen this creature enters, you may cast "
                "target instant card from your graveyard without paying its mana cost. If that spell would be put into your graveyard, "
                "exile it instead.", "5", "6", colors=("U",))
DWELLERS = real("Goblin Dark-Dwellers", "{3}{R}{R}", "Creature — Goblin", "Menace (This creature can't be blocked except by two or more "
                "creatures.)\nWhen this creature enters, you may cast target instant or sorcery card with mana value 3 or less from your "
                "graveyard without paying its mana cost. If that spell would be put into your graveyard, exile it instead.", "4", "4",
                colors=("R",))
SWORD = real("Sword of Once and Future", "{3}", "Artifact — Equipment", "Equipped creature gets +2/+2 and has protection from blue and "
             "from black.\nWhenever equipped creature deals combat damage to a player, surveil 2. Then you may cast an instant or sorcery "
             "spell with mana value 2 or less from your graveyard without paying its mana cost. If that spell would be put into your "
             "graveyard, exile it instead.\nEquip {2}")
ONI = real("Silent-Blade Oni", "{3}{U}{U}{B}{B}", "Creature — Demon Ninja", "Ninjutsu {4}{U}{B} ({4}{U}{B}, Return an unblocked attacker "
           "you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever this creature deals "
           "combat damage to a player, look at that player's hand. You may cast a spell from among those cards without paying its mana "
           "cost.", "6", "5", colors=("U", "B"))
WEALTH = real("Villainous Wealth", "{X}{B}{G}{U}", "Sorcery", "Target opponent exiles the top X cards of their library. You may cast any "
              "number of spells with mana value X or less from among them without paying their mana costs.", colors=("B", "G", "U"))
OPT = real("Opt", "{U}", "Instant", "Draw a card.", colors=("U",))
THREE = real("Three Drop", "{2}{U}", "Sorcery", "Draw a card.", colors=("U",))
FOUR = real("Four Drop", "{3}{U}", "Instant", "Draw a card.", colors=("U",))
JOLT = real("Jolt", "{1}{U}", "Instant", "Draw a card.", colors=("U",))


def asking(policy, asked):
    """`policy`, noting every list of options it is shown."""
    return lambda prompt, options: asked.append(list(options)) or policy(prompt, options)


class GraveyardTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GEARHULK, DWELLERS, SWORD, ONI, WEALTH):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_torrential_gearhulk_casts_an_instant_from_your_graveyard_and_exiles_it(self):
        asked = []
        game, _ = table3(asking(pick("Yes"), asked))
        a = game.seats[0]
        a.graveyard, a.library = [THREE, OPT], [FOREST] * 3
        enter(game, a, GEARHULK)
        run_stack(game)
        self.assertNotIn("Three Drop (seat 0 graveyard)", [o for options in asked for o in options])  # a sorcery: not an instant
        self.assertEqual(([c.name for c in a.graveyard], [c.name for c in a.exile], len(a.hand)), (["Three Drop"], ["Opt"], 1))

    def test_declining_leaves_the_instant_in_the_graveyard(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        a.graveyard, a.library = [OPT], [FOREST] * 3
        enter(game, a, GEARHULK)
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], a.exile, a.hand), (["Opt"], [], []))

    def test_goblin_dark_dwellers_takes_an_instant_or_sorcery_of_mana_value_three_or_less(self):
        asked = []
        game, _ = table3(asking(pick("Yes", "Three Drop"), asked))
        a = game.seats[0]
        a.graveyard, a.library = [FOUR, THREE], [FOREST] * 3
        enter(game, a, DWELLERS)
        run_stack(game)
        self.assertNotIn("Four Drop (seat 0 graveyard)", [o for options in asked for o in options])
        self.assertEqual(([c.name for c in a.graveyard], [c.name for c in a.exile], len(a.hand)), (["Four Drop"], ["Three Drop"], 1))

    def test_sword_of_once_and_future_casts_a_cheap_spell_from_the_graveyard_and_exiles_it(self):
        asked = []
        game, _ = table3(asking(pick("Jolt"), asked))
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        a.battlefield, a.graveyard, a.library = [bear, Permanent(SWORD, attached_to=bear)], [THREE, JOLT], [FOREST] * 4
        game.damage(b, 2, bear, combat=True)
        run_stack(game)
        self.assertNotIn("Three Drop", [o for options in asked for o in options])  # mana value 3: more than 2
        self.assertEqual(([c.name for c in a.exile], "Three Drop" in [c.name for c in a.graveyard]), (["Jolt"], True))


class HandAndLibraryTests(unittest.TestCase):
    def test_silent_blade_oni_casts_a_spell_from_the_hand_of_the_player_it_hit(self):
        asked = []
        game, _ = table3(asking(pick("Big"), asked))
        a, b, _ = game.seats
        oni = Permanent(ONI)
        a.battlefield, b.hand = [oni], [FOREST, BIG]
        game.damage(b, 6, oni, combat=True)
        run_stack(game)
        self.assertNotIn("Forest", [o for options in asked for o in options])  # a land is not a spell
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in b.hand]), (["Silent-Blade Oni", "Big"], ["Forest"]))

    def test_villainous_wealth_casts_the_spells_of_mana_value_x_or_less_among_the_exiled_cards(self):
        asked = []

        def policy(prompt, options):
            return options.index("3") if X_PROMPT.matches(prompt) else pick("Bear", "Three Drop")(prompt, options)
        game, _ = table3(asking(policy, asked))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.library = lands(6), [WEALTH], [FOREST] * 3
        b.library = [BIG, FOREST, BEAR, THREE]
        game._perform(a, CAST + "Villainous Wealth")
        run_stack(game)
        self.assertNotIn("Big", [o for options in asked for o in options])  # mana value 5: more than X
        self.assertNotIn("Forest", [o for options in asked for o in options])  # a land is not a spell
        self.assertIn("Bear", [p.card.name for p in a.battlefield])
        self.assertEqual(([c.name for c in b.exile], [c.name for c in b.library]), (["Big", "Forest"], ["Three Drop"]))


if __name__ == "__main__":
    unittest.main()
