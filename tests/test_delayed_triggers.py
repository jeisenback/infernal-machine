"""Delayed triggered abilities (CR 603.7): "Whenever you cast a creature spell this turn, draw a card." and "Until the end of your next
turn, whenever you cast a spell, ... deals 2 damage to up to one target creature." A resolved spell sets the ability up; it lasts
through the turn (or through its controller's next turn). Glimpse of Nature, Death Frenzy, Vizkopa Guildmage, Season of the Bold."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, KICKER_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, creature, lands, real, run_stack, script

GLIMPSE = real("Glimpse of Nature", "{G}", "Sorcery", "Whenever you cast a creature spell this turn, draw a card.", colors=("G",))
FRENZY = real("Death Frenzy", "{3}{B}{G}", "Sorcery", "All creatures get -2/-2 until end of turn. Whenever a creature dies this turn, "
              "you gain 1 life.", colors=("B", "G"))
GUILDMAGE = real("Vizkopa Guildmage", "{W}{B}", "Creature — Human Wizard", "{1}{W}{B}: Target creature gains lifelink until end of turn.\n"
                 "{1}{W}{B}: Whenever you gain life this turn, each opponent loses that much life.", "2", "2", colors=("B", "W"))
BOLD = real("Season of the Bold", "{3}{R}{R}", "Sorcery", "Choose up to five {P} worth of modes. You may choose the same mode more than once.\n"
            "{P} — Create a tapped Treasure token.\n{P}{P} — Exile the top two cards of your library. Until the end of your next turn, "
            "you may play them.\n{P}{P}{P} — Until the end of your next turn, whenever you cast a spell, Season of the Bold deals 2 damage "
            "to up to one target creature.", colors=("R",))
CRESCENDO = real("Gnawing Crescendo", "{2}{R}", "Instant", "Creatures you control get +2/+0 until end of turn. Whenever a nontoken creature you "
                 "control dies this turn, create a 1/1 black Rat creature token with \"This token can't block.\"", colors=("R",))
FRENZY_KICKER = real("Warhost's Frenzy", "{2}{R}", "Instant", "Kicker {B} (You may pay an additional {B} as you cast this spell.)\n"
                     "Creatures you control get +2/+0 until end of turn. If this spell was kicked, whenever a creature you control dies this "
                     "turn, draw a card.", colors=("R",))
CHEAP_SPELL = real("Cheap Spell", "{1}", "Sorcery", "You gain 1 life.")
FLASH_BEAR = creature("Flash Bear", 2, 2, "Flash")
CREATURE_SPELL = creature("Bear", 2, 2)
LIBRARY = [Card(name=f"Card {i}", type_line="Land") for i in range(12)]


def cast(table, card, seat=None):
    seat = seat or table.a
    seat.hand.append(card)
    table.game._perform(seat, CAST + card.name)
    run_stack(table.game)
    table.game._check_state()


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


class GlimpseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GLIMPSE, FRENZY, GUILDMAGE, BOLD):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_creature_spell_draws_a_card(self):
        t = Table(GLIMPSE, n=8, library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 0)
        cast(t, CREATURE_SPELL)
        self.assertEqual(len(t.a.hand), 1)

    def test_every_creature_spell_this_turn_draws(self):
        t = Table(GLIMPSE, n=8, library=LIBRARY).cast()
        cast(t, CREATURE_SPELL)
        cast(t, OGRE)
        self.assertEqual(len(t.a.hand), 2)

    def test_a_spell_that_is_not_a_creature_does_not(self):
        t = Table(GLIMPSE, n=8, library=LIBRARY).cast()
        cast(t, CHEAP_SPELL)
        self.assertEqual(len(t.a.hand), 0)

    def test_nothing_before_it_resolves(self):
        t = Table(GLIMPSE, n=8, library=LIBRARY)
        cast(t, CREATURE_SPELL)
        self.assertEqual(len(t.a.hand), 1)  # Glimpse of Nature itself is still in hand

    def test_an_opponent_casting_a_creature_does_not_draw_for_you(self):
        t = Table(GLIMPSE, n=8, library=LIBRARY).cast()
        t.b.battlefield = lands(4)
        cast(t, FLASH_BEAR, seat=t.b)
        self.assertEqual(len(t.a.hand), 0)

    def test_it_ends_with_the_turn(self):
        t = Table(GLIMPSE, n=8, library=LIBRARY).cast()
        end_turn(t.game, t.a)
        self.assertEqual(t.game.delayed, [])
        cast(t, CREATURE_SPELL)
        self.assertEqual(len(t.a.hand), 0)


class OtherTriggersTests(unittest.TestCase):
    def test_a_creature_dying_this_turn_gains_life(self):
        t = Table(FRENZY, n=8, mine=[Permanent(OGRE), Permanent(BEAR)], theirs=[Permanent(BEAR)], library=LIBRARY)
        life = t.a.life
        t.cast()
        run_stack(t.game)
        self.assertEqual(t.a.life, life + 2)  # both Bears die to -2/-2; the Ogre lives
        end_turn(t.game, t.a)
        self.assertEqual(t.game.delayed, [])

    def drain_table(self):
        t = Table(CHEAP_SPELL, n=8, mine=[Permanent(GUILDMAGE)], library=LIBRARY)
        t.game._perform(t.a, next(a for a in t.game.legal_actions(t.a) if a.endswith("each opponent loses that much life.")))
        run_stack(t.game)
        return t

    def test_gaining_life_drains_each_opponent(self):
        t = self.drain_table()
        self.assertEqual(len(t.game.delayed), 1)
        before = (t.b.life, t.c.life)
        cast(t, CHEAP_SPELL)  # you gain 1 life
        run_stack(t.game)
        self.assertEqual((t.b.life, t.c.life), (before[0] - 1, before[1] - 1))

    def test_an_opponent_gaining_life_does_not(self):
        t = self.drain_table()
        before = (t.a.life, t.c.life)
        t.game.change_life(t.b, 3)
        run_stack(t.game)
        self.assertEqual((t.a.life, t.c.life), before)

    def test_it_ends_with_the_turn(self):
        t = self.drain_table()
        end_turn(t.game, t.a)
        before = t.b.life
        cast(t, CHEAP_SPELL)
        self.assertEqual(t.b.life, before)


def kick(kicked):
    """Policy: answer the kicker question, pass otherwise."""
    return lambda prompt, options: (0 if kicked else 1) if prompt.startswith(KICKER_PROMPT) else options.index("Pass") if "Pass" in options else 0


class DiesThisTurnTests(unittest.TestCase):
    def test_a_nontoken_creature_dying_makes_a_rat(self):
        t = Table(CRESCENDO, n=8, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        t.game.destroy(next(p for p in t.a.battlefield if p.card.name == "Bear"))
        run_stack(t.game)
        self.assertEqual([p.card.name for p in t.a.battlefield if "Creature" in p.card.type_line], ["Rat"])

    def test_a_token_dying_does_not(self):
        token = Permanent(Card(name="Spirit", type_line="Token Creature \u2014 Spirit", power="1", toughness="1"))
        t = Table(CRESCENDO, n=8, mine=[token], library=LIBRARY).cast()
        t.game.destroy(token)
        run_stack(t.game)
        self.assertEqual([p.card.name for p in t.a.battlefield if "Creature" in p.card.type_line], [])

    def test_kicked_it_draws_when_a_creature_dies(self):
        t = Table(FRENZY_KICKER, policy=kick(True), n=8, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        t.game.destroy(next(p for p in t.a.battlefield if p.card.name == "Bear"))
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1)

    def test_not_kicked_it_does_not(self):
        t = Table(FRENZY_KICKER, policy=kick(False), n=8, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        self.assertEqual(t.game.delayed, [])
        t.game.destroy(next(p for p in t.a.battlefield if p.card.name == "Bear"))
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)


class BoldTests(unittest.TestCase):
    def table(self, **kwargs):
        return Table(BOLD, policy=script("{P}{P}{P}", "Done", "Ogre"), n=8, library=LIBRARY, **kwargs)

    def test_it_deals_damage_when_you_cast_a_spell(self):
        t = self.table(theirs=[Permanent(OGRE)])
        t.cast()
        self.assertEqual(len(t.game.delayed), 1)
        self.assertEqual(t.b.battlefield[0].damage, 0)
        cast(t, CHEAP_SPELL)
        self.assertEqual(t.b.battlefield[0].damage, 2)

    def test_each_spell_deals_damage_again(self):
        t = self.table(theirs=[Permanent(OGRE)])
        t.cast()
        cast(t, CHEAP_SPELL)
        cast(t, CHEAP_SPELL)
        self.assertEqual(len(t.b.battlefield), 0)  # two hits of 2 kill the Ogre

    def test_an_opponent_casting_does_not(self):
        t = self.table(theirs=[Permanent(OGRE)])
        t.cast()
        t.b.battlefield += lands(4)
        cast(t, FLASH_BEAR, seat=t.b)
        self.assertEqual(t.b.battlefield[0].damage, 0)

    def test_it_lasts_through_the_end_of_your_next_turn(self):
        t = self.table(theirs=[Permanent(OGRE)])
        t.cast()
        end_turn(t.game, t.a)  # this turn's cleanup
        self.assertEqual(len(t.game.delayed), 1)
        t.game.turn, t.game.active = 3, 1
        end_turn(t.game, t.b)  # an opponent's turn
        self.assertEqual(len(t.game.delayed), 1)
        t.game.turn, t.game.active = 5, 0
        cast(t, CHEAP_SPELL)
        self.assertEqual(t.b.battlefield[0].damage, 2)  # on your next turn it still works
        end_turn(t.game, t.a)
        self.assertEqual(t.game.delayed, [])  # and that turn's cleanup ends it
        cast(t, CHEAP_SPELL)
        self.assertEqual(t.b.battlefield[0].damage, 0)


if __name__ == "__main__":
    unittest.main()
