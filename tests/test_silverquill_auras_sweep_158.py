"""The eight Silverquill Auras of the precon decks that no test named (issue #158), each cast from its real Oracle text and enchanted
onto a creature, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, CAST_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, battlefield_names, real
from tests.test_triggers_80 import FOREST, PLAINS, RELIC, SHRINE

RED_BOLT = real("Red Bolt", "{R}", "Instant", "Red Bolt deals 3 damage to target creature.", colors=("R",))
BLUE_BOLT = real("Blue Bolt", "{U}", "Instant", "Blue Bolt deals 1 damage to target creature.", colors=("U",))
CHEAP = real("Cheap Creature", "{2}", "Creature — Test", "", "1", "1")


def aura_on(table, host):
    return next(p for p in table.a.battlefield + table.b.battlefield if p.attached_to is host)


def the(seat, name):
    return next(p for p in seat.battlefield if p.card.name == name)


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


COERCIVE = real("Coercive Impetus", "{2}{B}", "Enchantment — Aura",
                "Enchant creature\nEnchanted creature gets +1/+1 and is goaded. (It attacks each combat if able and attacks a player other "
                "than you if able.)\nWhenever enchanted creature attacks, you draw a card and lose 1 life.")
PARASITIC = real("Parasitic Impetus", "{2}{B}", "Enchantment — Aura",
                 "Enchant creature\nEnchanted creature gets +2/+2 and is goaded. (It attacks each combat if able and attacks a player other "
                 "than you if able.)\nWhenever enchanted creature attacks, its controller loses 2 life and you gain 2 life.")


class ImpetusTests(unittest.TestCase):
    def enchant(self, aura, host_owner):
        t = Table(aura, "Bear", mine=[], theirs=[])
        host = Permanent(BEAR, sick=False)
        (t.a if host_owner == 0 else t.b).battlefield.append(host)
        t.a.library = [FOREST] * 5
        t.cast()
        return t, host

    def attack(self, t, host):
        t.game.active = 1 if host in t.b.battlefield else 0
        t.b.player.policy = lambda prompt, options: 0
        t.game.combat.declare_attackers(t.game.seats[t.game.active])
        run_stack(t.game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(COERCIVE), [])
        self.assertEqual(unsupported_lines(PARASITIC), [])

    def test_coercive_gives_plus_one_plus_one(self):
        t, host = self.enchant(COERCIVE, 1)
        self.assertEqual((t.game.power(host), t.game.toughness(host)), (3, 3))

    def test_parasitic_gives_plus_two_plus_two(self):
        t, host = self.enchant(PARASITIC, 1)
        self.assertEqual((t.game.power(host), t.game.toughness(host)), (4, 4))

    def test_the_goaded_creature_must_attack_and_not_the_aura_controller(self):
        t, host = self.enchant(COERCIVE, 1)
        self.attack(t, host)
        self.assertEqual([a.defender for a in t.game.combat.attacks], [t.c])  # it attacks the third player, not me

    def test_coercive_draws_a_card_and_costs_a_life_when_it_attacks(self):
        t, host = self.enchant(COERCIVE, 1)
        hand_before = len(t.a.hand)
        self.attack(t, host)
        self.assertEqual((len(t.a.hand) - hand_before, t.a.life), (1, 39))

    def test_parasitic_drains_the_creatures_controller_for_two_when_it_attacks(self):
        t, host = self.enchant(PARASITIC, 1)
        self.attack(t, host)
        self.assertEqual((t.a.life, t.b.life), (42, 38))

    def test_nothing_happens_when_a_different_creature_attacks(self):
        t, host = self.enchant(COERCIVE, 1)
        other = Permanent(OGRE, sick=False)
        t.b.battlefield.append(other)
        host.sick = True
        self.attack(t, host)
        self.assertEqual((len(t.a.hand), t.a.life), (0, 40))

    def test_on_my_own_creature_the_goad_makes_it_attack_a_player_that_is_not_me(self):
        t, host = self.enchant(COERCIVE, 0)
        self.attack(t, host)
        self.assertNotIn(t.a, [a.defender for a in t.game.combat.attacks])
        self.assertEqual(len(t.game.combat.attacks), 1)


SHIELDED = real("Shielded by Faith", "{1}{W}{W}", "Enchantment — Aura",
                "Enchant creature\nEnchanted creature has indestructible.\nWhenever a creature enters, you may attach this Aura to that creature.")


class ShieldedByFaithTests(unittest.TestCase):
    def table(self, answer="Yes"):
        t = Table(SHIELDED, "Bear", mine=[])
        self.host = Permanent(BEAR)
        t.a.battlefield.append(self.host)
        t.cast()
        t.a.player.policy = pick(answer)
        return t

    def test_parse(self):
        self.assertEqual(unsupported_lines(SHIELDED), [])

    def test_the_enchanted_creature_is_indestructible(self):
        t = self.table()
        t.game.destroy(self.host)
        self.assertIn(self.host, t.a.battlefield)

    def test_a_creature_entering_may_take_the_aura_and_the_old_host_loses_it(self):
        t = self.table("Yes")
        newcomer = Permanent(OGRE)
        t.game._enter(t.a, newcomer)
        run_stack(t.game)
        self.assertTrue(t.game.has_keyword(newcomer, "indestructible"))
        self.assertFalse(t.game.has_keyword(self.host, "indestructible"))

    def test_it_may_stay_where_it_is(self):
        t = self.table("No")
        newcomer = Permanent(OGRE)
        t.game._enter(t.a, newcomer)
        run_stack(t.game)
        self.assertFalse(t.game.has_keyword(newcomer, "indestructible"))
        self.assertTrue(t.game.has_keyword(self.host, "indestructible"))

    def test_an_opponents_creature_entering_can_take_it_too(self):
        t = self.table("Yes")
        theirs = Permanent(OGRE)
        t.game._enter(t.b, theirs)
        run_stack(t.game)
        self.assertTrue(t.game.has_keyword(theirs, "indestructible"))

    def test_a_noncreature_entering_does_nothing(self):
        t = self.table("Yes")
        t.game._enter(t.a, Permanent(RELIC))
        run_stack(t.game)
        self.assertTrue(t.game.has_keyword(self.host, "indestructible"))


CHAINS = real("Chains of Custody", "{2}{W}", "Enchantment — Aura",
              "Enchant creature you control\nWhen this Aura enters, exile target nonland permanent an opponent controls until this Aura leaves "
              "the battlefield.\nEnchanted creature has ward {2}. (Whenever it becomes the target of a spell or ability an opponent controls, "
              "counter it unless that player pays {2}.)")
SHELTERED = real("Sheltered by Ghosts", "{1}{W}", "Enchantment — Aura",
                 "Enchant creature you control\nWhen this Aura enters, exile target nonland permanent an opponent controls until this Aura "
                 "leaves the battlefield.\nEnchanted creature gets +1/+0 and has lifelink and ward {2}.")


class ExilingAuraTests(unittest.TestCase):
    def enchant(self, aura, target="Ogre", theirs=None):
        t = Table(aura, "Bear", target, theirs=theirs if theirs is not None else [Permanent(OGRE), Permanent(FOREST), Permanent(RELIC)])
        self.host = Permanent(BEAR)
        t.a.battlefield.append(self.host)
        t.cast()
        return t

    def test_parse(self):
        self.assertEqual(unsupported_lines(CHAINS), [])
        self.assertEqual(unsupported_lines(SHELTERED), [])

    def test_entering_it_exiles_an_opposing_nonland_permanent(self):
        for aura in (CHAINS, SHELTERED):
            t = self.enchant(aura)
            self.assertEqual(battlefield_names(t.b), ["Forest", "Relic"], aura.name)
            self.assertIn("Ogre", [c.name for c in t.b.exile])

    def test_it_returns_when_the_aura_leaves_the_battlefield(self):
        t = self.enchant(CHAINS)
        t.game.destroy(aura_on(t, self.host))
        run_stack(t.game)
        self.assertEqual(battlefield_names(t.b), ["Forest", "Ogre", "Relic"])

    def test_it_returns_when_the_enchanted_creature_dies_and_takes_the_aura_with_it(self):
        t = self.enchant(SHELTERED)
        t.game.destroy(self.host)
        t.game._check_state()
        run_stack(t.game)
        self.assertIn("Ogre", battlefield_names(t.b))

    def test_lands_and_my_own_permanents_are_not_choices(self):
        t = self.enchant(CHAINS, target="Forest", theirs=[Permanent(FOREST)])
        self.assertEqual(battlefield_names(t.b), ["Forest"])
        self.assertEqual(t.b.exile, [])

    def test_it_can_only_enchant_a_creature_you_control(self):
        t = Table(CHAINS, "Ogre", mine=[], theirs=[Permanent(OGRE)])
        self.assertFalse(any(a.startswith(CAST + "Chains of Custody") for a in t.game.legal_actions(t.a)))

    def test_sheltered_by_ghosts_gives_plus_one_plus_zero_and_lifelink(self):
        t = self.enchant(SHELTERED)
        self.assertEqual((t.game.power(self.host), t.game.toughness(self.host)), (3, 2))
        self.assertTrue(t.game.has_keyword(self.host, "lifelink"))

    def test_chains_of_custody_gives_no_bonus_only_ward(self):
        t = self.enchant(CHAINS)
        self.assertEqual((t.game.power(self.host), t.game.has_keyword(self.host, "lifelink")), (2, False))

    def cast_at(self, aura, bolt, opponent_lands):
        t = self.enchant(aura)
        t.b.hand, t.b.battlefield = [bolt], lands(opponent_lands)
        t.game.active = 1
        t.b.player.policy = pick("Bear")
        t.game._perform(t.b, CAST + bolt.name)
        run_stack(t.game)
        return t

    def test_ward_two_counters_a_spell_unless_its_caster_pays(self):
        for aura in (CHAINS, SHELTERED):
            t = self.cast_at(aura, RED_BOLT, 1)
            self.assertEqual(self.host.damage, 0, aura.name)
            t = self.cast_at(aura, RED_BOLT, 3)
            self.assertEqual(self.host.damage, 3, aura.name)


RAFFINE = real("Raffine's Guidance", "{W}", "Enchantment — Aura",
               "Enchant creature\nEnchanted creature gets +1/+1.\nYou may cast this card from your graveyard by paying {2}{W} rather than "
               "paying its mana cost.")


class RaffinesGuidanceTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(RAFFINE), [])

    def test_it_gives_plus_one_plus_one(self):
        bear = Permanent(BEAR)
        t = Table(RAFFINE, "Bear", mine=[bear]).cast()
        self.assertEqual((t.game.power(bear), t.game.toughness(bear)), (3, 3))

    def graveyard(self, n, bear=None):
        t = Table(RAFFINE, "Bear", n=n, graveyard=[RAFFINE], mine=[bear or Permanent(BEAR)])
        t.a.hand = []
        return t

    def test_from_the_graveyard_it_costs_two_and_a_white(self):
        t = self.graveyard(3)
        self.assertIn(CAST_GRAVEYARD + "Raffine's Guidance", t.game.legal_actions(t.a))
        self.assertNotIn(CAST_GRAVEYARD + "Raffine's Guidance", self.graveyard(2).game.legal_actions(self.graveyard(2).a))

    def test_cast_from_the_graveyard_it_enchants_a_creature(self):
        bear = Permanent(BEAR)
        t = self.graveyard(3, bear)
        t.game._perform(t.a, CAST_GRAVEYARD + "Raffine's Guidance")
        run_stack(t.game)
        self.assertEqual((t.game.power(bear), t.a.graveyard), (3, []))

    def test_it_can_be_recast_again_after_it_dies_with_its_creature(self):
        bear = Permanent(BEAR)
        t = self.graveyard(3, bear)
        t.game._perform(t.a, CAST_GRAVEYARD + "Raffine's Guidance")
        run_stack(t.game)
        t.game.destroy(bear)
        t.game._check_state()
        run_stack(t.game)
        self.assertEqual([c.name for c in t.a.graveyard if c.name == "Raffine's Guidance"], ["Raffine's Guidance"])

    def test_it_is_not_castable_from_the_graveyard_without_a_creature(self):
        t = Table(RAFFINE, n=6, graveyard=[RAFFINE])
        self.assertNotIn(CAST_GRAVEYARD + "Raffine's Guidance", t.game.legal_actions(t.a))


EYES = real("Sentinel's Eyes", "{W}", "Enchantment — Aura",
            "Enchant creature\nEnchanted creature gets +1/+1 and has vigilance.\nEscape—{W}, Exile two other cards from your graveyard. (You may "
            "cast this card from your graveyard for its escape cost.)")


class SentinelsEyesTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(EYES), [])

    def test_it_gives_plus_one_plus_one_and_vigilance(self):
        bear = Permanent(BEAR)
        t = Table(EYES, "Bear", mine=[bear]).cast()
        self.assertEqual((t.game.power(bear), t.game.has_keyword(bear, "vigilance")), (3, True))

    def escape(self, others, n=1):
        bear = Permanent(BEAR)
        t = Table(EYES, "Bear", n=n, graveyard=[EYES, *others], mine=[bear])
        t.a.hand = []
        return t, bear

    def test_escape_costs_a_white_and_two_other_graveyard_cards(self):
        t, bear = self.escape([RELIC, SHRINE, FOREST])
        t.game._perform(t.a, CAST_GRAVEYARD + "Sentinel's Eyes")
        run_stack(t.game)
        self.assertEqual((t.game.has_keyword(bear, "vigilance"), len(t.a.exile)), (True, 2))
        self.assertEqual(len(t.a.graveyard), 1)

    def test_it_needs_two_other_cards(self):
        t, bear = self.escape([RELIC])
        self.assertNotIn(CAST_GRAVEYARD + "Sentinel's Eyes", t.game.legal_actions(t.a))

    def test_it_needs_the_white_mana(self):
        t, bear = self.escape([RELIC, SHRINE], n=0)
        self.assertNotIn(CAST_GRAVEYARD + "Sentinel's Eyes", t.game.legal_actions(t.a))

    def test_the_aura_itself_is_not_one_of_the_two_cards(self):
        t, bear = self.escape([RELIC, SHRINE])
        t.game._perform(t.a, CAST_GRAVEYARD + "Sentinel's Eyes")
        run_stack(t.game)
        self.assertEqual(sorted(c.name for c in t.a.exile), ["Relic", "Shrine"])


MANTLE = real("Spirit Mantle", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+1 and has protection from creatures.")


class SpiritMantleTests(unittest.TestCase):
    def mantled(self):
        bear = Permanent(BEAR, sick=False)
        t = Table(MANTLE, "Bear", mine=[bear]).cast()
        return t, bear

    def test_parse(self):
        self.assertEqual(unsupported_lines(MANTLE), [])

    def test_plus_one_plus_one(self):
        t, bear = self.mantled()
        self.assertEqual((t.game.power(bear), t.game.toughness(bear)), (3, 3))

    def test_creatures_cannot_block_it(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        bear = Permanent(BEAR, sick=False)
        a.battlefield = [bear, Permanent(MANTLE, attached_to=bear)]
        b.battlefield = [Permanent(OGRE, sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        self.assertEqual(game.combat.attacks[0].blockers, [])

    def test_damage_from_a_creature_is_prevented(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        bear = Permanent(BEAR, sick=False)
        b.battlefield = [Permanent(MANTLE, attached_to=bear), bear]
        a.battlefield = [Permanent(OGRE, sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(bear.damage, 0)

    def test_a_noncreature_source_can_still_hurt_it(self):
        t, bear = self.mantled()
        t.game.damage(bear, 3)
        t.game._check_state()
        self.assertNotIn(bear, t.a.battlefield)

    def test_a_creature_cannot_target_it_with_an_ability_but_a_spell_can(self):
        t, bear = self.mantled()
        self.assertTrue(t.game.protected_from(bear, frozenset({"creature"})))
        self.assertFalse(t.game.protected_from(bear, frozenset({"R"})))
