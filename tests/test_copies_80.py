"""The copy lines of issue #80 (Rionya first). Lines are the cards' own Oracle text from Scryfall; each has cases where the
effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_triggers_80 import card

RIONYA = Card(name="Rionya, Fire Dancer", mana_cost="{2}{R}{R}", type_line="Legendary Creature — Human Wizard", power="3", toughness="4",
              oracle_text="At the beginning of combat on your turn, create X tokens that are copies of another target creature you "
                          "control, where X is one plus the number of instant and sorcery spells you've cast this turn. They gain "
                          "haste. Exile them at the beginning of the next end step.")
BOLT = Card(name="Bolt", mana_cost="{R}", cmc=1.0, type_line="Instant")
RITUAL = Card(name="Ritual", mana_cost="{1}{R}", cmc=2.0, type_line="Sorcery")
BEAR_CARD = Card(name="Bear", mana_cost="{1}{G}", cmc=2.0, type_line="Creature — Bear", power="2", toughness="2")


class RionyaTests(unittest.TestCase):
    def combat(self, cast=(), target="Bear"):
        game, _ = table3(pick(target))
        a = game.seats[0]
        self.bear = Permanent(BEAR_CARD)
        a.battlefield = [Permanent(RIONYA), self.bear]
        for spell in cast:
            a.cast_log.append((game.turn, spell))
        game.step = "beginning_of_combat"
        game._turn_based_actions(a)
        run_stack(game)
        return game, a

    def copies(self, seat):
        return [p for p in seat.battlefield if p is not self.bear and p.card.name == "Bear"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(RIONYA), [])

    def test_one_copy_with_no_spells_cast(self):
        game, a = self.combat()
        [copy] = self.copies(a)
        self.assertTrue(game.has_keyword(copy, "haste"))

    def test_one_more_for_each_instant_or_sorcery_cast_this_turn(self):
        game, a = self.combat([BOLT, RITUAL])
        self.assertEqual(len(self.copies(a)), 3)

    def test_creature_spells_and_earlier_turns_do_not_count(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        self.bear = Permanent(BEAR_CARD)
        a.battlefield = [Permanent(RIONYA), self.bear]
        a.cast_log += [(game.turn, BEAR_CARD), (game.turn - 1, BOLT)]
        game.step = "beginning_of_combat"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(len(self.copies(a)), 1)

    def test_the_copies_are_exiled_at_the_next_end_step(self):
        game, a = self.combat([BOLT])
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(self.copies(a), [])
        self.assertEqual([c.name for c in a.graveyard if c.name == "Bear"], [])  # exiled, not sacrificed

    def test_exiling_is_not_dying(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        self.bear = Permanent(BEAR_CARD)
        a.battlefield = [Permanent(RIONYA), self.bear, Permanent(card(
            "Whenever a creature you control dies, you gain 1 life.", "Witness", "Enchantment"))]
        game.step = "beginning_of_combat"
        game._turn_based_actions(a)
        run_stack(game)
        life = a.life
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual((self.copies(a), a.life), ([], life))

    def test_the_target_is_another_creature_not_rionya(self):
        game, a = self.combat(target="Rionya")
        self.assertEqual([p for p in a.battlefield if p.card.name == "Rionya, Fire Dancer"][1:], [])


STORMSINGER = card("First strike\nWhenever this creature attacks, for each creature token you control that entered this turn, "
                   "create a tapped and attacking token that's a copy of that token. At the beginning of the next end step, "
                   "sacrifice those tokens.", "Stormsinger", "Creature — Orc Wizard")
SOLDIER = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1")
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure", oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")


class RedoubledStormsingerTests(unittest.TestCase):
    def attack(self):
        picks = iter([2])
        policy = lambda prompt, options: next(picks, 0) if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(policy)
        a, b, c = game.seats
        self.singer = Permanent(STORMSINGER, sick=False)
        self.fresh = Permanent(SOLDIER, sick=True, entered_turn=game.turn)
        self.old = Permanent(SOLDIER, sick=True, entered_turn=game.turn - 1)
        self.card = Permanent(BEAR_CARD, sick=True, entered_turn=game.turn)
        self.treasure = Permanent(TREASURE, entered_turn=game.turn)
        a.battlefield = [self.singer, self.fresh, self.old, self.card, self.treasure]
        game.combat.declare_attackers(a)
        run_stack(game)
        return game, a

    def copies(self, game, a):
        return [at for at in game.combat.attacks if at.attacker not in a.battlefield[:5]]

    def test_parse(self):
        self.assertEqual(unsupported_lines(STORMSINGER), [])

    def test_a_tapped_attacking_copy_of_each_token_that_entered_this_turn(self):
        game, a = self.attack()
        [copy] = self.copies(game, a)
        self.assertEqual((copy.attacker.card.name, copy.attacker.tapped), ("Soldier", True))
        self.assertIs(copy.defender, next(at.defender for at in game.combat.attacks if at.attacker is self.singer))

    def test_older_tokens_nontokens_and_noncreatures_are_not_copied(self):
        game, a = self.attack()
        self.assertEqual(len(self.copies(game, a)), 1)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Treasure"]), 1)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Bear"]), 1)

    def test_the_copies_are_sacrificed_at_the_next_end_step(self):
        game, a = self.attack()
        game.step = "end"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Soldier"]), 2)  # the two originals remain
