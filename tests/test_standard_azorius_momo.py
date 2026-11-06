"""Standard's Azorius Momo deck, from its cards' real Oracle text: Guiding Hydra (remove a counter to give each other creature one),
Nurturing Pixie (return a non-Faerie, nonland permanent; a counter if one was returned), Practiced Offense (counters on each creature a
player controls; a keyword of your choice) and Sage of the Skies (copy this spell if another was cast this turn)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, fire, lands, real, run_stack, script, table3

HYDRA = real("Guiding Hydra", "{X}{W}", "Creature — Hydra Horror", "This creature enters with X +1/+1 counters on it.\nAt the beginning of "
             "combat on your turn, you may remove a +1/+1 counter from this creature. If you do, put a +1/+1 counter on each other creature "
             "you control.", "1", "0", colors=("W",))
PIXIE = real("Nurturing Pixie", "{W}", "Creature — Faerie Rogue", "Flying\nWhen this creature enters, return up to one target non-Faerie, "
             "nonland permanent you control to its owner's hand. If a permanent was returned this way, put a +1/+1 counter on this "
             "creature.", "1", "1", colors=("W",))
OFFENSE = real("Practiced Offense", "{2}{W}", "Sorcery", "Put a +1/+1 counter on each creature target player controls. Target creature gains "
               "your choice of double strike or lifelink until end of turn.\nFlashback {1}{W} (You may cast this card from your graveyard for "
               "its flashback cost. Then exile it.)", colors=("W",))
SAGE = real("Sage of the Skies", "{2}{W}", "Creature — Human Monk", "When you cast this spell, if you've cast another spell this turn, copy "
            "this spell. (The copy becomes a token.)\nFlying, lifelink", "2", "3", colors=("W",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
FAERIE = real("Faerie", "{1}{U}", "Creature — Faerie", "", "1", "1", colors=("U",))


def table(*answers, battlefield=(), hand=()):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield, a.hand = list(battlefield), list(hand)
    for seat in game.seats:
        seat.library = [FOREST] * 5
    return game, a, b, c


class StandardAzoriusMomoTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (HYDRA, PIXIE, OFFENSE, SAGE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_guiding_hydra_moves_a_counter_onto_each_other_creature(self):
        hydra, bear, ogre = Permanent(HYDRA, counters={"+1/+1": 2}), Permanent(BEAR), Permanent(OGRE)
        game, a, b, _ = table("Yes", battlefield=[hydra, bear, ogre])
        b.battlefield = [Permanent(BEAR)]
        fire(game, a, hydra, "combat")
        self.assertEqual([p.counters.get("+1/+1") for p in (hydra, bear, ogre)], [1, 1, 1])
        self.assertIsNone(b.battlefield[0].counters.get("+1/+1"))

    def test_guiding_hydra_may_keep_its_counter(self):
        hydra, bear = Permanent(HYDRA, counters={"+1/+1": 2}), Permanent(BEAR)
        game, a, _, _ = table("No", battlefield=[hydra, bear])
        fire(game, a, hydra, "combat")
        self.assertEqual((hydra.counters.get("+1/+1"), bear.counters.get("+1/+1")), (2, None))

    def test_guiding_hydra_without_a_counter_gives_none(self):
        hydra, bear = Permanent(HYDRA), Permanent(BEAR)
        game, a, _, _ = table("Yes", battlefield=[hydra, bear])
        fire(game, a, hydra, "combat")
        self.assertIsNone(bear.counters.get("+1/+1"))

    def test_nurturing_pixie_returns_a_permanent_and_grows(self):
        bear = Permanent(BEAR)
        game, a, _, _ = table("Bear", battlefield=lands(1) + [bear, Permanent(FAERIE)], hand=[PIXIE])
        game._perform(a, CAST + "Nurturing Pixie")
        run_stack(game)
        pixie = next(p for p in a.battlefield if p.card is PIXIE)
        self.assertEqual(([c.name for c in a.hand], pixie.counters.get("+1/+1")), (["Bear"], 1))

    def test_nurturing_pixie_returning_nothing_gets_no_counter(self):
        game, a, _, _ = table(battlefield=lands(1) + [Permanent(FAERIE)], hand=[PIXIE])  # a Faerie is not a legal target
        game._perform(a, CAST + "Nurturing Pixie")
        run_stack(game)
        pixie = next(p for p in a.battlefield if p.card is PIXIE)
        self.assertEqual((a.hand, pixie.counters.get("+1/+1")), ([], None))

    def test_practiced_offense_counters_a_players_creatures_and_grants_the_chosen_keyword(self):
        bear, ogre, theirs = Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)
        game, a, b, _ = table("Player: B", "Ogre", "lifelink", battlefield=lands(3) + [bear, ogre], hand=[OFFENSE])
        b.battlefield = [theirs]
        game._perform(a, CAST + "Practiced Offense")
        run_stack(game)
        self.assertEqual([p.counters.get("+1/+1") for p in (bear, ogre, theirs)], [None, None, 1])  # the target player's creatures
        self.assertEqual((game.has_keyword(ogre, "lifelink"), game.has_keyword(ogre, "double strike")), (True, False))

    def test_practiced_offense_with_its_target_player_gone_still_grants_the_keyword(self):
        ogre, theirs = Permanent(OGRE), Permanent(BEAR)
        game, a, b, _ = table("Player: B", "Ogre", "double strike", battlefield=lands(3) + [ogre], hand=[OFFENSE])
        b.battlefield = [theirs]
        game._perform(a, CAST + "Practiced Offense")
        b.lost = True  # the player left the game before it resolved: that target is illegal
        run_stack(game)
        self.assertEqual((theirs.counters.get("+1/+1"), game.has_keyword(ogre, "double strike")), (None, True))

    def test_sage_of_the_skies_is_copied_after_another_spell(self):
        game, a, _, _ = table(battlefield=lands(4), hand=[OPT, SAGE])
        game._perform(a, CAST + "Opt")
        run_stack(game)
        game._perform(a, CAST + "Sage of the Skies")
        run_stack(game)
        sages = [p for p in a.battlefield if p.card.name == "Sage of the Skies"]
        self.assertEqual(len(sages), 2)

    def test_sage_of_the_skies_alone_is_not_copied(self):
        game, a, _, _ = table(battlefield=lands(3), hand=[SAGE])
        game._perform(a, CAST + "Sage of the Skies")
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Sage of the Skies"]), 1)


if __name__ == "__main__":
    unittest.main()
