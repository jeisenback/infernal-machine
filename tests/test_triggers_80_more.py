"""Trigger lines from the five precon decks that #80 listed and the report still marked unsupported (real Oracle text from
Scryfall). Each has cases where the trigger must not fire.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire

PAY = lambda prompt, options: 0
DECLINE = lambda prompt, options: len(options) - 1

TOMIK = Card(name="Tomik, Wielder of Law", mana_cost="{3}{W}{U}", type_line="Legendary Creature — Human Advisor", power="4",
             toughness="3", oracle_text="Flying\nWhenever an opponent attacks with creatures, if two or more of those creatures "
                                        "are attacking you and/or planeswalkers you control, that opponent loses 3 life and you "
                                        "draw a card.")
TRAITOR = Card(name="Nether Traitor", mana_cost="{B}{B}", type_line="Creature — Spirit", power="1", toughness="1",
               oracle_text="Haste\nWhenever another creature is put into your graveyard from the battlefield, you may pay {B}. If "
                           "you do, return this card from your graveyard to the battlefield.")


class TomikTests(unittest.TestCase):
    def attack(self, count):
        game, _ = table3()
        a, b, c = game.seats
        tomik = Permanent(TOMIK)
        a.battlefield = [tomik]
        a.library = [BEAR] * 5
        game.trigger("opponent_attacks", tomik, a, player=b, x=count)
        run_stack(game)
        return a, b, c

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(TOMIK), [])

    def test_two_attackers_at_you_costs_that_opponent_three_life_and_draws_you_a_card(self):
        a, b, c = self.attack(2)
        self.assertEqual((b.life, c.life, a.life, len(a.hand)), (37, 40, 40, 1))

    def test_one_attacker_at_you_does_nothing(self):
        a, b, c = self.attack(1)
        self.assertEqual((b.life, len(a.hand)), (40, 0))

    def combat(self, targets):
        """Player B declares two attackers; `targets` are the options picked for them (1 is seat 0, 2 is seat 2)."""
        picks = iter(targets)
        policy = lambda prompt, options: next(picks) if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(None, policy)
        a, b, c = game.seats
        tomik = Permanent(TOMIK)
        a.battlefield = [tomik]
        a.library = [BEAR] * 5
        b.battlefield = [Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)]
        game.active = 1
        game.combat.declare_attackers(b)
        run_stack(game)
        return a, b

    def test_in_real_combat_two_attackers_aimed_at_you_trigger_it(self):
        a, b = self.combat([1, 1])
        self.assertEqual((b.life, len(a.hand)), (37, 1))

    def test_in_real_combat_attackers_split_between_players_do_not(self):
        a, b = self.combat([1, 2])  # one at you, one at the third player
        self.assertEqual((b.life, len(a.hand)), (40, 0))


class NetherTraitorTests(unittest.TestCase):
    def die(self, owner_index, policy=PAY, mana=1, token=False):
        game, _ = table3(policy)
        a, b, c = game.seats
        a.graveyard, a.battlefield = [TRAITOR], lands(mana)
        card = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1") if token else BEAR
        victim = Permanent(card)
        game.seats[owner_index].battlefield.append(victim)
        game._leave_together([(victim, "destroyed")])
        run_stack(game)
        return a

    def graveyard(self, seat):
        return [c.name for c in seat.graveyard]

    def creatures(self, seat):
        return [p.card.name for p in seat.battlefield if "Creature" in p.card.type_line]

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(TRAITOR), [])

    def test_another_creature_of_yours_dying_and_paying_b_brings_it_back(self):
        a = self.die(0)
        self.assertEqual((self.creatures(a), self.graveyard(a)), (["Nether Traitor"], ["Bear"]))
        self.assertEqual(sum(p.tapped for p in a.battlefield if "Land" in p.card.type_line), 1)  # {B} was paid

    def test_a_token_of_yours_counts_too(self):
        a = self.die(0, token=True)
        self.assertEqual(self.creatures(a), ["Nether Traitor"])

    def test_declining_to_pay_leaves_it_in_the_graveyard(self):
        a = self.die(0, policy=DECLINE)
        self.assertEqual((self.creatures(a), "Nether Traitor" in self.graveyard(a)), ([], True))

    def test_without_mana_it_stays(self):
        a = self.die(0, mana=0)
        self.assertEqual((self.creatures(a), "Nether Traitor" in self.graveyard(a)), ([], True))

    def test_an_opponents_creature_dying_does_nothing(self):
        a = self.die(1)
        self.assertEqual((self.creatures(a), "Nether Traitor" in self.graveyard(a)), ([], True))


PIANIST = Card(name="Prismari Pianist", mana_cost="{3}{U}{R}", type_line="Creature — Human Wizard", power="3", toughness="4",
               oracle_text="Whenever you cast an instant or sorcery spell, create a 1/1 blue and red Elemental creature token. If "
                           "that spell's mana value is 5 or greater, create three of those tokens instead.")


def spell(name, mana_value, type_line="Instant", x=False):
    return Card(name=name, mana_cost=("{X}" if x else "") + "{%d}" % mana_value if mana_value else "", cmc=float(mana_value),
                type_line=type_line, oracle_text="Draw a card.")


class PrismariPianistTests(unittest.TestCase):
    def cast(self, card, caster=0, x=0):
        from infernal_machine.game import CAST
        policy = lambda prompt, options: (min(x, len(options) - 1) if prompt.startswith("Choose X") else
                                          next((i for i, o in enumerate(options) if o.startswith(CAST)), 0))
        game, _ = table3(policy, policy)
        a, b, c = game.seats
        a.battlefield = [Permanent(PIANIST)]
        game.seats[caster].battlefield += lands(9)
        game.seats[caster].hand = [card]
        game.seats[caster].library = [BEAR] * 5
        game.active, game.step = caster, "main1"
        game._perform(game.seats[caster], CAST + card.name)
        run_stack(game)
        return [p for p in a.battlefield if p.card.name == "Elemental"]

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(PIANIST), [])

    def test_a_small_spell_makes_one_token(self):
        self.assertEqual(len(self.cast(spell("Small", 2))), 1)

    def test_a_spell_with_mana_value_four_still_makes_one(self):
        self.assertEqual(len(self.cast(spell("Four", 4))), 1)

    def test_a_spell_with_mana_value_five_makes_three(self):
        self.assertEqual(len(self.cast(spell("Five", 5, "Sorcery"))), 3)

    def test_an_x_spell_counts_its_x_in_the_mana_value(self):
        self.assertEqual(len(self.cast(spell("Blast", 2, x=True), x=3)), 3)  # {X}{2} with X = 3 is mana value 5
        self.assertEqual(len(self.cast(spell("Blast", 2, x=True), x=1)), 1)

    def test_a_creature_spell_makes_none(self):
        self.assertEqual(self.cast(spell("Ogre", 6, "Creature — Ogre")), [])

    def test_an_opponents_spell_makes_none(self):
        self.assertEqual(self.cast(spell("Five", 5), caster=1), [])


HELLKITE = Card(name="Manaform Hellkite", mana_cost="{2}{R}{R}", type_line="Creature — Dragon", power="4", toughness="4",
                oracle_text="Flying, haste\nWhenever you cast a noncreature spell, create an X/X red Dragon Illusion creature token "
                            "with flying and haste, where X is the amount of mana spent to cast that spell. Exile that token at the "
                            "beginning of the next end step.")


class ManaformHellkiteTests(unittest.TestCase):
    def cast(self, card, caster=0):
        from infernal_machine.game import CAST
        policy = lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith(CAST)), 0)
        game, _ = table3(policy, policy)
        a, b, c = game.seats
        a.battlefield = [Permanent(HELLKITE)]
        game.seats[caster].battlefield += lands(6)
        game.seats[caster].hand = [card]
        game.seats[caster].library = [BEAR] * 5
        game.active, game.step = caster, "main1"
        game._perform(game.seats[caster], CAST + card.name)
        run_stack(game)
        return game, [p for p in a.battlefield if p.card.name == "Dragon Illusion"]

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(HELLKITE), [])

    def test_the_token_is_as_big_as_the_mana_spent(self):
        game, tokens = self.cast(spell("Three", 3))
        [token] = tokens
        self.assertEqual((token.card.power, token.card.toughness), ("3", "3"))
        self.assertEqual((game.has_keyword(token, "flying"), game.has_keyword(token, "haste")), (True, True))

    def test_a_bigger_spell_makes_a_bigger_token(self):
        game, tokens = self.cast(spell("Five", 5, "Sorcery"))
        self.assertEqual([t.card.power for t in tokens], ["5"])

    def test_it_is_exiled_at_the_beginning_of_the_next_end_step(self):
        game, tokens = self.cast(spell("Three", 3))
        game.step = "end"
        game._turn_based_actions(game.seats[0])
        run_stack(game)
        self.assertEqual([p for p in game.seats[0].battlefield if p.card.name == "Dragon Illusion"], [])
        self.assertEqual([c.name for c in game.seats[0].exile if c.name == "Dragon Illusion"], [])  # a token ceases to exist

    def test_a_creature_spell_makes_nothing(self):
        game, tokens = self.cast(spell("Ogre", 3, "Creature — Ogre"))
        self.assertEqual(tokens, [])

    def test_an_opponents_spell_makes_nothing(self):
        game, tokens = self.cast(spell("Three", 3), caster=1)
        self.assertEqual(tokens, [])


KILLIAN = Card(name="Killian, Decisive Mentor", mana_cost="{2}{W}{U}", type_line="Legendary Creature — Human Warlock", power="3",
               toughness="3", oracle_text="Whenever an enchantment you control enters, tap up to one target creature and goad it.\n"
                                          "Whenever one or more creatures that are enchanted by an Aura you control attack, draw a card.")
BLESSING = Card(name="Blessing", mana_cost="{1}{W}", type_line="Enchantment — Aura", oracle_text="Enchant creature")


class KillianTests(unittest.TestCase):
    def attack(self, attackers, active=0, auras=()):
        """`attackers` are (card, seat index, aura owner index or None); the active player attacks with all of them."""
        policy = lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(policy, policy, policy)
        a = game.seats[0]
        killian = Permanent(KILLIAN)
        a.battlefield = [killian]
        a.library = [BEAR] * 6
        for card, seat_index, aura_owner in attackers:
            creature = Permanent(card, sick=False)
            game.seats[seat_index].battlefield.append(creature)
            if aura_owner is not None:
                game.seats[aura_owner].battlefield.append(Permanent(BLESSING, attached_to=creature))
        game.active = active
        game.combat.declare_attackers(game.seats[active])
        run_stack(game)
        return a

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(KILLIAN), [])

    def test_an_attacking_creature_enchanted_by_your_aura_draws_a_card(self):
        a = self.attack([(BEAR, 0, 0)])
        self.assertEqual(len(a.hand), 1)

    def test_two_such_attackers_still_draw_one_card(self):
        a = self.attack([(BEAR, 0, 0), (OGRE, 0, 0)])
        self.assertEqual(len(a.hand), 1)

    def test_a_creature_enchanted_by_someone_elses_aura_does_not(self):
        a = self.attack([(BEAR, 0, 1)])
        self.assertEqual(a.hand, [])

    def test_an_unenchanted_attacker_does_not(self):
        a = self.attack([(BEAR, 0, None)])
        self.assertEqual(a.hand, [])

    def test_an_opponents_creature_enchanted_by_your_aura_does_when_it_attacks(self):
        a = self.attack([(BEAR, 1, 0)], active=1)
        self.assertEqual(len(a.hand), 1)


EIDOLON = Card(name="Hateful Eidolon", mana_cost="{3}{B}", type_line="Creature — Spirit", power="2", toughness="3",
               oracle_text="Deathtouch\nWhenever an enchanted creature dies, draw a card for each Aura you controlled that was "
                           "attached to it.")


class HatefulEidolonTests(unittest.TestCase):
    def die(self, mine, theirs, owner_index=0):
        """A creature on `owner_index`'s side dies with `mine` of Eidolon's controller's Auras and `theirs` of seat 1's on it."""
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(EIDOLON)]
        a.library = [BEAR] * 6
        victim = Permanent(OGRE)
        game.seats[owner_index].battlefield.append(victim)
        for _ in range(mine):
            a.battlefield.append(Permanent(BLESSING, attached_to=victim))
        for _ in range(theirs):
            b.battlefield.append(Permanent(BLESSING, attached_to=victim))
        game._leave_together([(victim, "destroyed")])
        run_stack(game)
        return a

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(EIDOLON), [])

    def test_one_card_for_each_of_your_auras_that_was_on_it(self):
        self.assertEqual(len(self.die(mine=2, theirs=0).hand), 2)

    def test_only_your_auras_count(self):
        self.assertEqual(len(self.die(mine=1, theirs=2).hand), 1)

    def test_a_creature_with_no_aura_draws_nothing(self):
        self.assertEqual(self.die(mine=0, theirs=0).hand, [])

    def test_a_creature_enchanted_only_by_an_opponents_aura_draws_nothing(self):
        self.assertEqual(self.die(mine=0, theirs=2).hand, [])

    def test_an_opponents_creature_dying_with_your_aura_counts(self):
        self.assertEqual(len(self.die(mine=1, theirs=0, owner_index=1).hand), 1)


MOURNER = Card(name="Aura Mourner", mana_cost="{1}{B}", type_line="Creature — Spirit", power="1", toughness="1",
               oracle_text="Whenever an enchanted creature dies, you gain 1 life.")


class EnchantedCreatureDiesTests(unittest.TestCase):
    def die(self, auras):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(MOURNER)]
        victim = Permanent(OGRE)
        b.battlefield.append(victim)
        for _ in range(auras):
            c.battlefield.append(Permanent(BLESSING, attached_to=victim))  # anyone's Aura makes it enchanted
        game._leave_together([(victim, "destroyed")])
        run_stack(game)
        return a.life

    def test_a_creature_with_an_aura_on_it_triggers_it(self):
        self.assertEqual(self.die(1), 41)

    def test_a_creature_without_one_does_not(self):
        self.assertEqual(self.die(0), 40)
