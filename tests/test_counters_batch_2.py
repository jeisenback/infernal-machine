"""Counters on permanents, batch 2, from the cards' real Oracle text: Unbreakable Formation and Sphinx's Insight (addendum: "If you cast this
spell during your main phase"), Tribute to the World Tree (draw, or two counters on a creature with less power), Innkeeper's Talent's level
2 ("Permanents you control with counters on them have ward {1}."), Tarrian's Soulcleaver (a counter on the equipped creature), Undying
Malice (it comes back tapped with a +1/+1 counter) and Luminous Broodmoth (a creature without flying comes back with a flying counter)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, enter, lands, pick, real, run_stack, table3

FORMATION = real("Unbreakable Formation", "{2}{W}", "Instant", "Creatures you control gain indestructible until end of turn.\nAddendum — If you "
                 "cast this spell during your main phase, put a +1/+1 counter on each of those creatures and they gain vigilance until end of "
                 "turn.", colors=("W",))
INSIGHT = real("Sphinx's Insight", "{2}{W}{U}", "Instant", "Draw two cards.\nAddendum — If you cast this spell during your main phase, you gain "
               "2 life.", colors=("W", "U"))
TRIBUTE = real("Tribute to the World Tree", "{G}{G}{G}", "Enchantment", "Whenever a creature you control enters, draw a card if its power is 3 "
               "or greater. Otherwise, put two +1/+1 counters on it.", colors=("G",))
TALENT = real("Innkeeper's Talent", "{1}{G}", "Enchantment — Class", "(Gain the next level as a sorcery to add its ability.)\nAt the beginning "
              "of combat on your turn, put a +1/+1 counter on target creature you control.\n{G}: Level 2\nPermanents you control with counters "
              "on them have ward {1}.\n{3}{G}: Level 3\nIf you would put one or more counters on a permanent or player, put twice that many of "
              "each of those kinds of counters on that permanent or player instead.", colors=("G",))
SOULCLEAVER = real("Tarrian's Soulcleaver", "{1}", "Legendary Artifact — Equipment", "Equipped creature has vigilance.\nWhenever another artifact "
                   "or creature is put into a graveyard from the battlefield, put a +1/+1 counter on equipped creature.\nEquip {2}")
MALICE = real("Undying Malice", "{B}", "Instant", "Until end of turn, target creature gains \"When this creature dies, return it to the "
              "battlefield tapped under its owner's control with a +1/+1 counter on it.\"", colors=("B",))
BROODMOTH = real("Luminous Broodmoth", "{2}{W}{W}", "Creature — Insect", "Flying\nWhenever a creature you control without flying dies, return "
                 "it to the battlefield under its owner's control with a flying counter on it.", "3", "4", colors=("W",))
CARDS = (FORMATION, INSIGHT, TRIBUTE, TALENT, SOULCLEAVER, MALICE, BROODMOTH)

DRAKE = real("Wind Drake", "{2}{U}", "Creature — Drake", "Flying", "2", "2", colors=("U",))


def cast(game, seat, card, n=6):
    seat.battlefield += lands(n)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


def on_battlefield(seat, card):
    return next((p for p in seat.battlefield if p.card is card), None)


class CountersBatch2Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_unbreakable_formation_adds_counters_only_in_your_main_phase(self):
        for step, active, added in (("main1", 0, True), ("combat", 0, False), ("main1", 1, False)):  # (on another player's turn: not yours)
            game, _ = table3()
            a = game.seats[0]
            game.step, game.active = step, active
            bear = Permanent(BEAR)
            a.battlefield = [bear]
            cast(game, a, FORMATION)
            self.assertEqual((bear.counters.get("+1/+1"), game.has_keyword(bear, "vigilance"), game.has_keyword(bear, "indestructible")),
                             (1 if added else None, added, True), (step, active))

    def test_sphinxs_insight_gains_life_only_in_your_main_phase(self):
        for step, life in (("main2", 42), ("end", 40)):
            game, _ = table3()
            a = game.seats[0]
            game.step, game.active, a.library = step, 0, [FOREST] * 3
            cast(game, a, INSIGHT)
            self.assertEqual((a.life, len(a.hand)), (life, 2), step)

    def test_tribute_draws_for_a_big_creature_and_grows_a_small_one(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(TRIBUTE)], [FOREST] * 3
        small = enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual((small.counters.get("+1/+1"), len(a.hand)), (2, 0))
        big = enter(game, a, OGRE)
        run_stack(game)
        self.assertEqual((big.counters.get("+1/+1"), len(a.hand)), (None, 1))

    def test_innkeepers_talent_gives_ward_to_permanents_with_counters_at_level_2(self):
        for level, warded in ((2, True), (1, False)):
            game, _ = table3()
            a = game.seats[0]
            countered, land, plain = Permanent(BEAR), Permanent(FOREST), Permanent(BEAR)
            countered.counters["+1/+1"] = 1
            land.counters["lore"] = 1  # any kind of counter, on any permanent
            a.battlefield = [countered, land, plain]
            talent = enter(game, a, TALENT)  # a Class enters at level 1
            run_stack(game)
            if level == 2:
                game.class_level_up(talent)
            self.assertEqual((game.has_keyword(countered, "ward {1}"), game.has_keyword(land, "ward {1}"), game.has_keyword(plain, "ward {1}")),
                             (warded, warded, False), level)

    def test_tarrians_soulcleaver_grows_the_creature_it_equips(self):
        for attached in (True, False):
            game, _ = table3()
            a = game.seats[0]
            bear, victim = Permanent(BEAR), Permanent(OGRE)
            a.battlefield = [bear, victim, Permanent(RELIC), Permanent(SOULCLEAVER, attached_to=bear if attached else None)]
            game.destroy(victim)
            game.destroy(a.battlefield[1])  # the Relic: an artifact too
            run_stack(game)
            self.assertEqual(bear.counters.get("+1/+1"), 2 if attached else None, attached)

    def test_undying_malice_returns_the_creature_tapped_with_a_counter(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        bear, other = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [bear, other]
        cast(game, a, MALICE, n=1)
        game.destroy(bear)
        game.destroy(other)  # no Malice on it: it stays dead
        run_stack(game)
        back = on_battlefield(a, BEAR)
        self.assertIsNotNone(back)
        assert back is not None
        self.assertEqual((back.tapped, back.counters.get("+1/+1"), on_battlefield(a, OGRE)), (True, 1, None))

    def test_luminous_broodmoth_returns_a_creature_without_flying_once(self):
        game, _ = table3()
        a = game.seats[0]
        bear, drake = Permanent(BEAR), Permanent(DRAKE)
        a.battlefield = [Permanent(BROODMOTH), bear, drake]
        game.destroy(bear)
        game.destroy(drake)  # it has flying: it stays dead
        run_stack(game)
        back = on_battlefield(a, BEAR)
        self.assertIsNotNone(back)
        assert back is not None
        self.assertEqual((back.counters.get("flying"), game.has_keyword(back, "flying"), on_battlefield(a, DRAKE)), (1, True, None))
        game.destroy(back)  # its flying counter: the second time it has flying, so it stays dead
        run_stack(game)
        self.assertIsNone(on_battlefield(a, BEAR))


if __name__ == "__main__":
    unittest.main()
