"""Standard's Jeskai Control deck, from its cards' real Oracle text: Ajani Unrelenting (a Cadet whenever you activate a loyalty ability;
4 damage to each creature but your tokens), Chandra, Torch of Defiance (cast the exiled top card or deal 2 to each opponent; her emblem),
Flashback (an instant or sorcery card gains flashback for its mana cost) and Ral, Crackling Wit (an emblem that gives storm)."""

import unittest

from infernal_machine.game import ACTIVATE, CAST, CAST_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, real, run_stack, script, table3

AJANI = real("Ajani Unrelenting", "{4}{R}{R}", "Legendary Planeswalker — Ajani", "Whenever you activate a loyalty ability, create a 2/2 "
             "colorless Wizard Soldier creature token named Cadet.\n+1: Creatures you control get +1/+0 and gain haste until end of turn.\n"
             "−2: Discard your hand, then draw a card for each creature you control.\n−3: Ajani deals 4 damage to each creature except for "
             "tokens you control.", colors=("R",))
CHANDRA = real("Chandra, Torch of Defiance", "{2}{R}{R}", "Legendary Planeswalker — Chandra", "+1: Exile the top card of your library. You "
               "may cast that card. If you don't, Chandra deals 2 damage to each opponent.\n+1: Add {R}{R}.\n−3: Chandra deals 4 damage to "
               "target creature.\n−7: You get an emblem with \"Whenever you cast a spell, this emblem deals 5 damage to any target.\"",
               colors=("R",))
FLASHBACK = real("Flashback", "{R}", "Instant", "Target instant or sorcery card in your graveyard gains flashback until end of turn. The "
                 "flashback cost is equal to its mana cost. (You may cast that card from your graveyard for its flashback cost. Then exile "
                 "it.)", colors=("R",))
RAL = real("Ral, Crackling Wit", "{2}{U}{R}", "Legendary Planeswalker — Ral", "Whenever you cast a noncreature spell, put a loyalty counter "
           "on Ral.\n+1: Create a 1/1 blue and red Otter creature token with prowess.\n−3: Draw three cards, then discard two cards.\n"
           "−10: Draw three cards. You get an emblem with \"Instant and sorcery spells you cast have storm.\" (Whenever you cast an instant "
           "or sorcery spell, copy it for each spell cast before it this turn.)", colors=("R", "U"))
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
OGRE = real("Ogre", "{2}{R}", "Creature — Ogre", "", "3", "3", colors=("R",))
GIANT = real("Giant", "{4}{R}", "Creature — Giant", "", "5", "5", colors=("R",))
MIND_STONE = real("Mind Stone", "{2}", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.")
VISION = real("Ancestral Vision", "", "Sorcery", "Suspend 4—{U} (Rather than cast this card from your hand, pay {U} and exile it with four time "
              "counters on it. At the beginning of your upkeep, remove a time counter. When the last is removed, you may cast it without "
              "paying its mana cost.)\nTarget player draws three cards.", colors=("U",))
CADET = real("Cadet", "", "Token Creature — Wizard Soldier", "", "2", "2")


def table(*answers, battlefield=(), hand=(), graveyard=(), library=None):
    game, _ = table3(script(*answers) if answers else None)
    a, b, c = game.seats
    a.battlefield, a.hand, a.graveyard = list(battlefield), list(hand), list(graveyard)
    for seat in game.seats:
        seat.library = list(library) if library is not None else [FOREST] * 5
    return game, a, b, c


def activate(game, seat, walker, cost):
    """Activate the loyalty ability of `walker` whose cost is `cost` ("+1", "−3")."""
    game._perform(seat, next(x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + walker) and f" {cost}: " in x))


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


class StandardJeskaiControlTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (AJANI, CHANDRA, FLASHBACK, RAL):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_ajani_makes_a_cadet_for_each_loyalty_ability(self):
        game, a, _, _ = table(battlefield=[Permanent(AJANI, loyalty=5)])
        activate(game, a, "Ajani Unrelenting", "+1")
        run_stack(game)
        self.assertEqual(names(a), ["Ajani Unrelenting", "Cadet"])

    def test_ajani_ignores_an_ability_that_is_not_a_loyalty_ability(self):
        game, a, _, _ = table(battlefield=[Permanent(AJANI, loyalty=5), Permanent(MIND_STONE)] + lands(1))
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Mind Stone") and "Draw" in x))
        run_stack(game)
        self.assertEqual(names(a), ["Ajani Unrelenting"])

    def test_ajanis_minus_three_spares_only_your_tokens(self):
        ajani, bear, cadet, theirs = Permanent(AJANI, loyalty=5), Permanent(BEAR), Permanent(CADET), Permanent(OGRE)
        game, a, b, _ = table(battlefield=[ajani, bear, cadet])
        b.battlefield = [theirs, Permanent(CADET)]
        activate(game, a, "Ajani Unrelenting", "−3")
        run_stack(game)
        game._check_state()
        self.assertEqual(names(a), ["Ajani Unrelenting", "Cadet", "Cadet"])  # the Bear died; the old Cadet and the new one live
        self.assertEqual(b.battlefield, [])  # an opponent's token is not spared

    def test_chandra_casts_the_exiled_card(self):
        game, a, b, _ = table("Yes", "Player: B", battlefield=lands(1) + [Permanent(CHANDRA, loyalty=4)], library=[SHOCK, FOREST])
        activate(game, a, "Chandra, Torch of Defiance", "+1")
        run_stack(game)
        self.assertEqual((b.life, game.seats[2].life, a.graveyard), (38, 40, [SHOCK]))

    def test_chandra_deals_two_to_each_opponent_when_the_card_is_not_cast(self):
        game, a, b, c = table(battlefield=[Permanent(CHANDRA, loyalty=4)], library=[GIANT, FOREST])  # no mana for the Giant
        activate(game, a, "Chandra, Torch of Defiance", "+1")
        run_stack(game)
        self.assertEqual((b.life, c.life, a.exile), (38, 38, [GIANT]))

    def test_chandras_emblem_deals_five_whenever_you_cast_a_spell(self):
        game, a, b, _ = table("Player: B", battlefield=lands(1) + [Permanent(CHANDRA, loyalty=7)], hand=[OPT])
        activate(game, a, "Chandra, Torch of Defiance", "−7")
        run_stack(game)
        self.assertEqual(len(a.emblems), 1)
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual(b.life, 35)

    def test_flashback_lets_an_instant_be_cast_again_this_turn(self):
        game, a, b, _ = table("Shock", "Player: B", battlefield=lands(2), hand=[FLASHBACK], graveyard=[SHOCK])
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_GRAVEYARD)], [])
        game._perform(a, CAST + "Flashback")
        run_stack(game)
        game._perform(a, CAST_GRAVEYARD + "Shock")
        run_stack(game)
        self.assertEqual((b.life, a.exile), (38, [SHOCK]))


    def test_a_granted_flashback_lasts_only_this_turn(self):
        game, a, _, _ = table("Shock", battlefield=lands(2), hand=[FLASHBACK], graveyard=[SHOCK])
        game._perform(a, CAST + "Flashback")
        run_stack(game)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_GRAVEYARD)], [CAST_GRAVEYARD + "Shock"])
        game.turn += 1
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_GRAVEYARD)], [])

    def test_a_card_without_a_mana_cost_gets_no_free_flashback(self):
        game, a, _, _ = table("Ancestral Vision", battlefield=lands(1), hand=[FLASHBACK], graveyard=[VISION])
        game._perform(a, CAST + "Flashback")
        run_stack(game)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST_GRAVEYARD)], [])

    def test_flashback_cannot_target_a_creature_card(self):
        game, a, _, _ = table(battlefield=lands(1), hand=[FLASHBACK], graveyard=[BEAR])
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST + "Flashback")], [])

    def test_rals_emblem_gives_instants_storm(self):
        game, a, b, _ = table("Player: B", "Player: B", "Player: B", battlefield=lands(2) + [Permanent(RAL, loyalty=10)], hand=[OPT, SHOCK])
        a.library = [FOREST] * 10
        activate(game, a, "Ral, Crackling Wit", "−10")
        run_stack(game)
        game._perform(a, CAST + "Opt")
        run_stack(game)
        game._perform(a, CAST + "Shock")
        run_stack(game)
        self.assertEqual(b.life, 36)  # the Shock and one copy for the Opt cast before it

    def test_rals_emblem_does_not_give_a_creature_spell_storm(self):
        game, a, b, _ = table(battlefield=lands(3) + [Permanent(RAL, loyalty=10)], hand=[OPT, BEAR])
        a.library = [FOREST] * 10
        activate(game, a, "Ral, Crackling Wit", "−10")
        run_stack(game)
        game._perform(a, CAST + "Opt")
        run_stack(game)
        game._perform(a, CAST + "Bear")
        run_stack(game)
        self.assertEqual(names(a).count("Bear"), 1)

    def test_without_the_emblem_there_is_no_storm(self):
        game, a, b, _ = table("Player: B", "Player: B", battlefield=lands(2), hand=[OPT, SHOCK])
        game._perform(a, CAST + "Opt")
        run_stack(game)
        game._perform(a, CAST + "Shock")
        run_stack(game)
        self.assertEqual(b.life, 38)


if __name__ == "__main__":
    unittest.main()
