"""A delayed ability about the creature a spell or ability targeted (CR 603.7): "Whenever that creature deals combat damage to a player or
planeswalker this turn, draw that many cards." (Hunter's Insight), "Whenever that creature attacks one of your opponents this turn, you draw
a card." (Maeve), "... attacks the monarch this turn, it gains double strike and trample" (Okoye), "if this spell was kicked" (Vigorous Charge)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import KICKER_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, creature, lands, real, run_stack, script
from tests.test_delayed_triggers import end_turn

HUNTER = real("Hunter's Insight", "{2}{G}", "Instant", "Choose target creature you control. Whenever that creature deals combat damage to a "
              "player or planeswalker this turn, draw that many cards.", colors=("G",))
CHARGE = real("Vigorous Charge", "{G}", "Instant", "Kicker {W} (You may pay an additional {W} as you cast this spell.)\nTarget creature gains "
              "trample until end of turn. Whenever that creature deals combat damage this turn, if this spell was kicked, you gain life equal to "
              "that damage.", colors=("G",))
MAEVE = real("Maeve, Insidious Singer", "{2}{U}{U}", "Legendary Creature — Siren", "{2}{U}: Goad target creature. Whenever that creature "
             "attacks one of your opponents this turn, you draw a card. (A goaded creature attacks each combat if able and attacks a player "
             "other than you if able, until your next turn.)\nWhenever you cast a spell with mana value 6 or greater, ...", "2", "4", colors=("U",))
OKOYE = real("Okoye, Mighty and Adored", "{2}{G}{W}", "Legendary Creature — Human Warrior Hero", "When Okoye enters, you become the monarch.\n"
             "At the beginning of combat on your turn, put a +1/+1 counter on target creature. Whenever that creature attacks the monarch this "
             "turn, it gains double strike and trample until end of turn.", "3", "3", colors=("G", "W"))
CHEAP = real("Cheap Spell", "{1}", "Sorcery", "You gain 1 life.")
LIBRARY = [Card(name=f"Card {i}", type_line="Land") for i in range(12)]
KICK = lambda kicked: lambda prompt, options: (0 if kicked else 1) if KICKER_PROMPT.matches(prompt) else (
    options.index("Pass") if "Pass" in options else 0)


def cast_on(card, *mine, policy=None):
    ogre = Permanent(OGRE)
    t = Table(card, policy=policy or script("Ogre"), n=8, mine=[ogre, *mine], library=LIBRARY).cast()
    return t, ogre


class HitTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (HUNTER, CHARGE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_combat_damage_to_a_player_draws_that_many(self):
        t, ogre = cast_on(HUNTER)
        t.game.damage(t.b, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 3)

    def test_combat_damage_to_a_planeswalker_draws_too(self):
        walker = Permanent(Card(name="Walker", type_line="Planeswalker — Test", loyalty="5"), loyalty=5)
        t, ogre = cast_on(HUNTER)
        t.b.battlefield.append(walker)
        t.game.damage(walker, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 3)

    def test_each_hit_this_turn_draws(self):
        t, ogre = cast_on(HUNTER)
        t.game.damage(t.b, 3, source=ogre, combat=True)
        t.game.damage(t.c, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 6)

    def test_combat_damage_to_a_creature_does_not(self):
        t, ogre = cast_on(HUNTER)
        t.b.battlefield.append(Permanent(BEAR))
        t.game.damage(t.b.battlefield[0], 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)

    def test_damage_that_is_not_combat_damage_does_not(self):
        t, ogre = cast_on(HUNTER)
        t.game.damage(t.b, 3, source=ogre, combat=False)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)

    def test_another_creature_does_not(self):
        other = Permanent(OGRE)
        t, ogre = cast_on(HUNTER, other)
        t.game.damage(t.b, 3, source=other, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)

    def test_it_ends_with_the_turn(self):
        t, ogre = cast_on(HUNTER)
        end_turn(t.game, t.a)
        t.game.damage(t.b, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0)


class KickedTests(unittest.TestCase):
    def test_kicked_it_gains_life_equal_to_the_damage(self):
        t, ogre = cast_on(CHARGE, policy=lambda p, o: KICK(True)(p, o) if p.startswith(KICKER_PROMPT) else script("Ogre")(p, o))
        life = t.a.life
        t.game.damage(t.b, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(t.a.life, life + 3)

    def test_not_kicked_it_does_not(self):
        t, ogre = cast_on(CHARGE, policy=lambda p, o: KICK(False)(p, o) if p.startswith(KICKER_PROMPT) else script("Ogre")(p, o))
        life = t.a.life
        t.game.damage(t.b, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(t.a.life, life)


class AttackTests(unittest.TestCase):
    def maeve(self):
        t = Table(CHEAP, policy=script("Ogre"), n=8, mine=[Permanent(MAEVE)], theirs=[Permanent(OGRE)], library=LIBRARY)
        t.game._perform(t.a, next(a for a in t.game.legal_actions(t.a) if "Goad target creature" in a))
        run_stack(t.game)
        return t, t.b.battlefield[0]

    def test_it_attacking_one_of_your_opponents_draws(self):
        t, goaded = self.maeve()
        t.game._remembered_attack(goaded, t.c)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1 + 1)  # the spell in hand and the card

    def test_it_attacking_you_does_not(self):
        t, goaded = self.maeve()
        t.game._remembered_attack(goaded, t.a)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1)


class MonarchTests(unittest.TestCase):
    def okoye(self):
        ogre = Permanent(OGRE)
        t = Table(CHEAP, policy=script("Ogre"), n=8, mine=[ogre, Permanent(OKOYE)], library=LIBRARY)
        t.game.trigger("combat", t.a.battlefield[1], t.a)
        run_stack(t.game)
        return t, ogre

    def test_it_attacking_the_monarch_gains_double_strike_and_trample(self):
        t, ogre = self.okoye()
        t.game.monarch = t.c
        t.game._remembered_attack(ogre, t.c)
        run_stack(t.game)
        self.assertTrue(t.game.has_keyword(ogre, "double strike") and t.game.has_keyword(ogre, "trample"))

    def test_a_real_attack_on_the_monarch(self):
        ogre = Permanent(OGRE, sick=False)
        attack = lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else script("Ogre")(prompt, options)
        t = Table(CHEAP, policy=attack, n=8, mine=[ogre, Permanent(OKOYE)], library=LIBRARY)
        t.game.trigger("combat", t.a.battlefield[1], t.a)
        run_stack(t.game)
        t.game.monarch = t.b
        t.game.combat.declare_attackers(t.a)
        run_stack(t.game)
        self.assertIn(ogre, [a.attacker for a in t.game.combat.attacks if a.defender is t.b])
        self.assertTrue(t.game.has_keyword(ogre, "double strike"))

    def test_it_attacking_someone_else_does_not(self):
        t, ogre = self.okoye()
        t.game.monarch = t.c
        t.game._remembered_attack(ogre, t.b)
        run_stack(t.game)
        self.assertFalse(t.game.has_keyword(ogre, "double strike"))


STARWINDER = real("Starwinder", "{4}{U}{U}", "Creature \u2014 Whale", "Whenever a creature you control deals combat damage to a player, you may draw that many cards.\n"
                  "Warp {2}{U}{U} (You may cast this card from your hand for its warp cost. Exile this creature at the beginning of the next end step, "
                  "then you may cast it from exile on a later turn.)", "7", "7", colors=("U",))
VILIS = real("Vilis, Broker of Blood", "{3}{B}{B}{B}", "Legendary Creature \u2014 Demon", "Flying\n{B}, Pay 2 life: Target creature gets -1/-1 until "
             "end of turn.\nWhenever you lose life, draw that many cards. (Damage causes loss of life.)", "5", "5", colors=("B",))


class ThatManyTests(unittest.TestCase):
    """The "draw that many cards" these cards share with the delayed ability: the number comes with the event."""

    def test_a_creature_you_control_dealing_combat_damage_draws_that_many(self):
        ogre = Permanent(OGRE)
        t = Table(CHEAP, n=8, mine=[Permanent(STARWINDER), ogre], library=LIBRARY)
        t.game.damage(t.b, 3, source=ogre, combat=True)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1 + 3)

    def test_losing_life_draws_that_many(self):
        t = Table(CHEAP, n=8, mine=[Permanent(VILIS)], library=LIBRARY)
        t.game.change_life(t.a, -3)
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 1 + 3)


if __name__ == "__main__":
    unittest.main()
