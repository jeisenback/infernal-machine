"""Dethrone and three clones, from the cards' real Oracle text: Treasonous Ogre (Dethrone, CR 702.105: a +1/+1 counter when it attacks the
player with the most life or tied for most life), Dack's Duplicate (a clone "except it has haste and dethrone"), Progenitor Mimic (a
clone with "At the beginning of your upkeep, if this creature isn't a token, create a token that's a copy of this creature.") and Jwari
Shapeshifter ("any Ally creature on the battlefield")."""

import unittest

from infernal_machine.game import CAST, CLONE_PROMPT, NOT_A_COPY, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, PASS, fire, lands, pick, real, run_stack, table, table3

TREASONOUS = real("Treasonous Ogre", "{3}{R}", "Creature — Ogre Shaman", "Dethrone (Whenever this creature attacks the player with the most "
                  "life or tied for most life, put a +1/+1 counter on it.)\nPay 3 life: Add {R}.", "2", "3", colors=("R",))
DACKS = real("Dack's Duplicate", "{2}{U}{R}", "Creature — Shapeshifter", "You may have this creature enter as a copy of any creature on the "
             "battlefield, except it has haste and dethrone. (Whenever it attacks the player with the most life or tied for most life, put a "
             "+1/+1 counter on it.)", "0", "0", colors=("R", "U"))
MIMIC = real("Progenitor Mimic", "{4}{G}{U}", "Creature — Shapeshifter", "You may have this creature enter as a copy of any creature on the "
             "battlefield, except it has \"At the beginning of your upkeep, if this creature isn't a token, create a token that's a copy of "
             "this creature.\"", "0", "0", colors=("G", "U"))
JWARI = real("Jwari Shapeshifter", "{1}{U}", "Creature — Shapeshifter Ally", "You may have this creature enter as a copy of any Ally creature "
             "on the battlefield.", "0", "0", colors=("U",))
CARDS = (TREASONOUS, DACKS, MIMIC, JWARI)
ALLY = real("Kazandu Blademaster", "{W}{W}", "Creature — Human Soldier Ally", "First strike, vigilance", "2", "2", colors=("W",))


def choosing(wanted):
    """Policy: cast the card and copy the permanent whose label starts with `wanted` (None: copy nothing); else pass."""
    def policy(prompt, options):
        if CLONE_PROMPT.matches(prompt):
            return options.index(NOT_A_COPY) if wanted is None else next(i for i, o in enumerate(options) if o.startswith(wanted))
        return next((i for i, o in enumerate(options) if o.startswith(CAST)), options.index(PASS) if PASS in options else 0)
    return policy


def enter(card, theirs=(), wanted=None):
    game, _, _ = table(choosing(wanted))
    a, b = game.seats
    a.hand, a.battlefield, b.battlefield = [card], lands(6), [Permanent(c) for c in theirs]
    game._priority_round(a)
    run_stack(game)
    return game, a, b


def copied(seat):
    return next(p for p in seat.battlefield if p.real_card is not None)


class DethroneAndClonesTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_dethrone_counts_only_against_the_player_with_the_most_life(self):
        for b_life, c_life, counters in ((40, 40, 1), (50, 40, 1), (30, 40, None)):  # tied, the most, and not the most
            game, _ = table3(pick("Attack Player: B"))
            a, b, c = game.seats
            ogre = Permanent(TREASONOUS)
            a.battlefield, b.life, c.life = [ogre], b_life, c_life
            game.combat.declare_attackers(a)
            run_stack(game)
            self.assertEqual(ogre.counters.get("+1/+1"), counters, (b_life, c_life))

    def test_dacks_duplicate_copies_with_haste_and_dethrone(self):
        game, a, b = enter(DACKS, theirs=[OGRE], wanted="Ogre")
        duplicate = copied(a)
        self.assertEqual((duplicate.card.name, game.has_keyword(duplicate, "haste"), game.has_keyword(duplicate, "dethrone")),
                         ("Ogre", True, True))

    def test_progenitor_mimic_copies_itself_each_upkeep_but_its_token_does_not(self):
        game, a, b = enter(MIMIC, theirs=[BEAR], wanted="Bear")
        mimic = copied(a)
        fire(game, a, mimic, "upkeep")
        tokens = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual([t.card.name for t in tokens], ["Bear"])
        fire(game, a, tokens[0], "upkeep")  # the token is a token: it makes nothing
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in a.battlefield), 1)

    def test_jwari_shapeshifter_copies_only_an_ally(self):
        offered = []
        def policy(prompt, options):
            if CLONE_PROMPT.matches(prompt):
                offered.extend(options)
            return choosing("Kazandu")(prompt, options)
        game, _, _ = table(policy)
        a, b = game.seats
        a.hand, a.battlefield, b.battlefield = [JWARI], lands(2), [Permanent(ALLY), Permanent(OGRE)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(copied(a).card.name, "Kazandu Blademaster")
        self.assertFalse(any(o.startswith("Ogre") for o in offered))


if __name__ == "__main__":
    unittest.main()
