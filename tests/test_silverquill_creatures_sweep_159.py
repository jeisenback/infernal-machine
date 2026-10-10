"""The nine Silverquill enchantment-matters creatures of the precon decks that no test named (issue #159), each played from its real
Oracle text, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, battlefield_names, real
from tests.test_triggers_80 import BIG, FOREST, PLAINS, RELIC, SHRINE
from tests.test_x_targets import script

AURA = real("Plain Aura", "{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+1.")
AURA_TWO = real("Second Aura", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+1.")
SWORD = real("Sword", "{2}", "Artifact — Equipment", "Equipped creature gets +1/+1.\nEquip {2}")
CAR = real("Car", "{2}", "Artifact — Vehicle", "Crew 1", "3", "3")
CANTRIP = real("Cantrip", "{W}", "Instant", "Draw a card.")
THREE_ENCHANTMENT = real("Big Shrine", "{2}{W}", "Enchantment", "")
BOLT = real("Bolt", "{2}", "Instant", "Bolt deals 3 damage to target creature.")
PLAYER_BOLT = real("Player Bolt", "{2}", "Instant", "Player Bolt deals 3 damage to target player.")
SPIRIT_TOKEN = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")


def enter(game, seat, card):
    permanent = Permanent(card, attached_to=None)
    game._enter(seat, permanent)
    run_stack(game)
    return permanent


def tokens(seat, name):
    return [p for p in seat.battlefield if p.card.name == name and p.card.type_line.startswith("Token")]


def end_step(game, seat):
    game.active = seat.index
    game.step = "end"
    game._turn_based_actions(seat)
    run_stack(game)


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


def fight(game, seat):
    game.active = seat.index
    game.combat.declare_attackers(seat)
    run_stack(game)
    game.combat.declare_blockers()
    run_stack(game)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)


CHOSEN = real("Ajani's Chosen", "{2}{W}{W}", "Creature — Cat Soldier",
              "Whenever an enchantment you control enters, create a 2/2 white Cat creature token. If that enchantment is an Aura, you may attach "
              "it to the token.", "3", "3")


class AjanisChosenTests(unittest.TestCase):
    def table(self, *answers):
        game, _ = table3(script(*answers))
        a, b, _ = game.seats
        a.battlefield = [Permanent(CHOSEN)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(CHOSEN), [])

    def test_an_enchantment_you_control_makes_a_two_two_cat(self):
        game, a, b = self.table()
        enter(game, a, SHRINE)
        [cat] = tokens(a, "Cat")
        self.assertEqual((game.power(cat), game.toughness(cat)), (2, 2))

    def test_an_enchantment_creature_counts(self):
        game, a, b = self.table()
        enter(game, a, real("Griffin", "{1}{W}", "Enchantment Creature — Griffin", "", "1", "2"))
        self.assertEqual(len(tokens(a, "Cat")), 1)

    def test_a_nonenchantment_or_an_opponents_enchantment_does_not(self):
        game, a, b = self.table()
        enter(game, a, RELIC)
        enter(game, b, SHRINE)
        self.assertEqual(len(tokens(a, "Cat")), 0)

    def test_an_aura_may_be_attached_to_the_cat(self):
        game, a, b = self.table("Yes")
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        aura = Permanent(AURA, attached_to=bear)
        game._enter(a, aura)
        run_stack(game)
        [cat] = tokens(a, "Cat")
        self.assertIs(aura.attached_to, cat)

    def test_the_aura_may_stay_where_it_is(self):
        game, a, b = self.table("No")
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        aura = Permanent(AURA, attached_to=bear)
        game._enter(a, aura)
        run_stack(game)
        self.assertIs(aura.attached_to, bear)

    def test_a_cat_is_made_even_when_the_aura_stays(self):
        game, a, b = self.table("No")
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        game._enter(a, Permanent(AURA, attached_to=bear))
        run_stack(game)
        self.assertEqual(len(tokens(a, "Cat")), 1)


ARCHON = real("Archon of Sun's Grace", "{2}{W}{W}", "Creature — Archon",
              "Flying\nLifelink (Damage dealt by this creature also causes you to gain that much life.)\nPegasus creatures you control have "
              "lifelink.\nConstellation — Whenever an enchantment you control enters, create a 2/2 white Pegasus creature token with flying.",
              "3", "4")
PEGASUS = real("Pegasus", "{1}{W}", "Creature — Pegasus", "Flying", "1", "1")


class ArchonOfSunsGraceTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.archon = Permanent(ARCHON)
        a.battlefield = [self.archon]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(ARCHON), [])

    def test_it_has_flying_and_lifelink_itself(self):
        game, a, b = self.table()
        self.assertTrue(game.has_keyword(self.archon, "flying") and game.has_keyword(self.archon, "lifelink"))

    def test_an_enchantment_makes_a_two_two_flying_pegasus_with_lifelink(self):
        game, a, b = self.table()
        enter(game, a, SHRINE)
        [pegasus] = tokens(a, "Pegasus")
        self.assertEqual((game.power(pegasus), game.toughness(pegasus)), (2, 2))
        self.assertTrue(game.has_keyword(pegasus, "flying") and game.has_keyword(pegasus, "lifelink"))

    def test_an_opponents_enchantment_or_a_nonenchantment_makes_none(self):
        game, a, b = self.table()
        enter(game, b, SHRINE)
        enter(game, a, RELIC)
        self.assertEqual(len(tokens(a, "Pegasus")), 0)

    def test_other_pegasi_you_control_gain_lifelink_but_other_creatures_and_opposing_pegasi_do_not(self):
        game, a, b = self.table()
        mine, other, theirs = Permanent(PEGASUS), Permanent(BEAR), Permanent(PEGASUS)
        a.battlefield += [mine, other]
        b.battlefield = [theirs]
        self.assertEqual([game.has_keyword(p, "lifelink") for p in (mine, other, theirs)], [True, False, False])

    def test_pegasi_lose_lifelink_when_the_archon_leaves(self):
        game, a, b = self.table()
        pegasus = Permanent(PEGASUS)
        a.battlefield.append(pegasus)
        game.destroy(self.archon)
        self.assertFalse(game.has_keyword(pegasus, "lifelink"))

    def test_lifelink_gains_life_in_combat(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(ARCHON, sick=False)]
        fight(game, a)
        self.assertEqual(a.life, 43)


SRAM = real("Sram, Senior Edificer", "{1}{W}", "Legendary Creature — Dwarf Advisor",
            "Whenever you cast an Aura, Equipment, or Vehicle spell, draw a card.", "2", "2")


class SramTests(unittest.TestCase):
    def cast(self, spell, *answers, opponent=False):
        t = Table(spell, *answers, mine=[Permanent(SRAM), Permanent(BEAR)])
        t.a.library = [FOREST] * 5
        t.b.library = [FOREST] * 5
        if opponent:
            t.b.hand, t.b.battlefield = [spell], lands(6)
            t.a.hand = []
            t.game.active = 1
            t.b.player.policy = pick("Bear")
            t.game._perform(t.b, CAST + spell.name)
            run_stack(t.game)
            return t
        return t.cast()

    def test_parse(self):
        self.assertEqual(unsupported_lines(SRAM), [])

    def test_casting_an_aura_an_equipment_or_a_vehicle_draws_a_card(self):
        for spell, answers in ((AURA, ("Bear",)), (SWORD, ()), (CAR, ())):
            t = self.cast(spell, *answers)
            self.assertEqual(len(t.a.hand), 1, spell.name)

    def test_other_spells_do_not(self):
        for spell in (CANTRIP, SHRINE, RELIC):
            t = self.cast(spell)
            self.assertEqual(len(t.a.hand), 1 if spell is CANTRIP else 0, spell.name)  # the Cantrip draws for itself only

    def test_an_opponents_aura_does_not(self):
        t = self.cast(AURA, opponent=True)
        self.assertEqual(len(t.a.hand), 0)


MYSTIC = real("Starfield Mystic", "{1}{W}", "Creature — Human Cleric",
              "Enchantment spells you cast cost {1} less to cast.\nWhenever an enchantment you control is put into a graveyard from the "
              "battlefield, put a +1/+1 counter on this creature.", "2", "2")


class StarfieldMysticTests(unittest.TestCase):
    def castable(self, spell, n, mystic=True):
        t = Table(spell, "Bear", n=n, mine=[Permanent(MYSTIC)] if mystic else [Permanent(BEAR)])
        return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a))

    def test_parse(self):
        self.assertEqual(unsupported_lines(MYSTIC), [])

    def test_enchantment_spells_cost_one_less(self):
        self.assertTrue(self.castable(THREE_ENCHANTMENT, 2))
        self.assertFalse(self.castable(THREE_ENCHANTMENT, 2, mystic=False))

    def test_other_spells_do_not(self):
        self.assertFalse(self.castable(CANTRIP, 0))
        self.assertFalse(self.castable(real("Two Artifact", "{2}", "Artifact", ""), 1))

    def test_the_reduction_never_removes_colored_mana(self):
        self.assertFalse(self.castable(real("White Shrine", "{W}", "Enchantment", ""), 0))

    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.mystic = Permanent(MYSTIC)
        a.battlefield = [self.mystic]
        return game, a, b

    def test_an_enchantment_of_yours_dying_gives_it_a_counter(self):
        game, a, b = self.table()
        shrine = enter(game, a, SHRINE)
        game.destroy(shrine)
        run_stack(game)
        self.assertEqual(self.mystic.counters.get("+1/+1"), 1)

    def test_an_opponents_enchantment_or_a_nonenchantment_dying_does_not(self):
        game, a, b = self.table()
        theirs, relic = enter(game, b, SHRINE), enter(game, a, RELIC)
        game.destroy(theirs)
        game.destroy(relic)
        run_stack(game)
        self.assertEqual(self.mystic.counters.get("+1/+1"), None)

    def test_an_enchantment_that_is_bounced_does_not(self):
        game, a, b = self.table()
        shrine = enter(game, a, SHRINE)
        game.return_to_hand(shrine)
        run_stack(game)
        self.assertEqual(self.mystic.counters.get("+1/+1"), None)


GIANT = real("Doomwake Giant", "{4}{B}", "Enchantment Creature — Giant",
             "Constellation — Whenever this creature or another enchantment you control enters, creatures your opponents control get -1/-1 until "
             "end of turn.", "4", "6")


class DoomwakeGiantTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(GIANT)]
        self.small = Permanent(real("Small", "{1}", "Creature — Test", "", "1", "1"))
        self.theirs = Permanent(OGRE)
        b.battlefield = [self.small, self.theirs]
        self.mine = Permanent(BEAR)
        a.battlefield.append(self.mine)
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(GIANT), [])

    def test_casting_it_triggers_its_own_constellation(self):
        t = Table(GIANT, theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(t.game.power(t.b.battlefield[0]), 2)

    def test_another_enchantment_shrinks_opposing_creatures_and_kills_toughness_one(self):
        game, a, b = self.table()
        enter(game, a, SHRINE)
        game._check_state()
        self.assertEqual((game.power(self.theirs), game.toughness(self.theirs)), (2, 2))
        self.assertNotIn(self.small, b.battlefield)
        self.assertEqual(game.power(self.mine), 2)

    def test_it_wears_off_at_end_of_turn(self):
        game, a, b = self.table()
        enter(game, a, SHRINE)
        end_turn(game, a)
        self.assertEqual(game.power(self.theirs), 3)

    def test_a_nonenchantment_or_an_opponents_enchantment_does_nothing(self):
        game, a, b = self.table()
        enter(game, a, RELIC)
        enter(game, b, SHRINE)
        self.assertEqual(game.power(self.theirs), 3)

    def test_each_enchantment_stacks_another_minus_one(self):
        game, a, b = self.table()
        enter(game, a, SHRINE)
        enter(game, a, THREE_ENCHANTMENT)
        self.assertEqual(game.power(self.theirs), 1)


ERIETTE = real("Eriette of the Charmed Apple", "{1}{W}{B}", "Legendary Creature — Human Warlock",
               "Each creature that's enchanted by an Aura you control can't attack you or planeswalkers you control.\nAt the beginning of your "
               "end step, each opponent loses X life and you gain X life, where X is the number of Auras you control.", "2", "4")


class EriettesTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(ERIETTE), [])

    def test_the_end_step_drains_each_opponent_for_the_number_of_auras_you_control(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(ERIETTE), bear, Permanent(AURA, attached_to=bear), Permanent(AURA_TWO, attached_to=bear)]
        end_step(game, a)
        self.assertEqual((a.life, b.life, c.life), (42, 38, 38))

    def test_no_auras_no_drain_and_an_opponents_aura_does_not_count(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(ERIETTE), bear]
        b.battlefield = [Permanent(AURA, attached_to=bear)]
        end_step(game, a)
        self.assertEqual((a.life, b.life, c.life), (40, 40, 40))

    def test_only_at_your_own_end_step(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(ERIETTE), bear, Permanent(AURA, attached_to=bear)]
        end_step(game, b)
        self.assertEqual((a.life, b.life), (40, 40))

    def attackable(self, aura_owner):
        game, _ = table3(pick("Attack"))
        a, b, c = game.seats
        attacker = Permanent(BEAR, sick=False)
        b.battlefield = [attacker]
        a.battlefield = [Permanent(ERIETTE)]
        holder = a if aura_owner == 0 else c
        holder.battlefield.append(Permanent(AURA, attached_to=attacker))
        b.player.policy = pick("Attack Player: A", "Attack")
        game.active = 1
        game.combat.declare_attackers(b)
        return [att.defender for att in game.combat.attacks]

    def test_a_creature_enchanted_by_my_aura_cannot_attack_me(self):
        defenders = self.attackable(0)
        self.assertNotIn(None, defenders)
        self.assertEqual([d.index for d in defenders if d is not None], [2] if defenders else [])

    def test_a_creature_enchanted_by_someone_elses_aura_still_can(self):
        defenders = self.attackable(2)
        self.assertEqual([d.index for d in defenders], [0])


ENVOY = real("Transcendent Envoy", "{1}{W}", "Enchantment Creature — Griffin", "Flying\nAura spells you cast cost {1} less to cast.", "1", "2")
KILLIAN = real("Killian, Ink Duelist", "{W}{B}", "Legendary Creature — Human Warlock",
               "Lifelink\nMenace (This creature can't be blocked except by two or more creatures.)\nSpells you cast that target a creature "
               "cost {2} less to cast.", "2", "2")
COSTLY_AURA = real("Costly Aura", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +2/+2.")


class CostReducerTests(unittest.TestCase):
    def castable(self, spell, n, reducer, answers=("Bear",), mine_extra=()):
        t = Table(spell, *answers, n=n, mine=[Permanent(reducer), Permanent(BEAR), *mine_extra], theirs=[Permanent(OGRE)])
        return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a))

    def test_parse(self):
        self.assertEqual(unsupported_lines(ENVOY), [])
        self.assertEqual(unsupported_lines(KILLIAN), [])

    def test_envoy_makes_aura_spells_cost_one_less(self):
        self.assertTrue(self.castable(COSTLY_AURA, 1, ENVOY))
        self.assertFalse(self.castable(COSTLY_AURA, 1, BEAR))

    def test_envoy_reduces_by_exactly_one(self):
        three = real("Three Aura", "{2}{W}", "Enchantment — Aura", "Enchant creature")
        self.assertTrue(self.castable(three, 2, ENVOY))
        self.assertFalse(self.castable(three, 1, ENVOY))

    def test_envoy_leaves_other_spells_alone(self):
        self.assertFalse(self.castable(real("Two Spell", "{2}", "Instant", "Draw a card."), 1, ENVOY, answers=()))
        self.assertFalse(self.castable(THREE_ENCHANTMENT, 2, ENVOY, answers=()))

    def test_envoy_has_flying(self):
        game, _ = table3(pick())
        envoy = Permanent(ENVOY)
        self.assertTrue(game.has_keyword(envoy, "flying"))

    def test_killian_makes_spells_that_target_a_creature_cost_two_less(self):
        self.assertTrue(self.castable(BOLT, 0, KILLIAN, answers=("Ogre",)))
        self.assertFalse(self.castable(BOLT, 0, BEAR, answers=("Ogre",)))

    def test_killian_reduces_by_exactly_two(self):
        three = real("Three Bolt", "{3}", "Instant", "Three Bolt deals 3 damage to target creature.")
        self.assertTrue(self.castable(three, 1, KILLIAN, answers=("Ogre",)))
        self.assertFalse(self.castable(three, 0, KILLIAN, answers=("Ogre",)))

    def test_killian_does_not_reduce_a_spell_that_targets_a_player_or_nothing(self):
        self.assertFalse(self.castable(PLAYER_BOLT, 0, KILLIAN, answers=("Player: B",)))
        self.assertFalse(self.castable(CANTRIP, 0, KILLIAN, answers=()))

    def test_killian_never_reduces_the_colored_part(self):
        self.assertFalse(self.castable(real("Red Bolt", "{R}", "Instant", "Red Bolt deals 3 damage to target creature.", colors=("R",)), 0,
                                       KILLIAN, answers=("Ogre",)))

    def test_killian_has_lifelink_and_menace(self):
        game, _ = table3(pick())
        killian = Permanent(KILLIAN)
        self.assertTrue(game.has_keyword(killian, "lifelink") and game.has_keyword(killian, "menace"))


HERALD = real("Herald of Amity", "{3}{W}", "Creature — Griffin",
              "Flying\nWhen this creature enters, exile the top eight cards of your library. You may cast an Aura spell from among them without "
              "paying its mana cost. Then put the rest on the bottom of your library in a random order.\nWhenever this creature attacks, it gets "
              "+X/+X until end of turn, where X is the number of Auras you control.", "2", "2")
FILLER = [real(f"Filler {i}", "{1}", "Sorcery", "") for i in range(12)]


class HeraldOfAmityTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(HERALD), [])

    def cast(self, library, *answers, creature=True):
        t = Table(HERALD, *answers, library=library, mine=[Permanent(BEAR)] if creature else [])
        return t.cast()

    def test_it_may_cast_an_aura_from_the_top_eight_free_and_the_rest_go_to_the_bottom(self):
        library = FILLER[:3] + [AURA] + FILLER[3:10]
        t = self.cast(library, "Plain Aura", "Bear")
        bear = next(p for p in t.a.battlefield if p.card.name == "Bear")
        self.assertEqual(t.game.power(bear), 3)
        self.assertEqual(len(t.a.library), len(library) - 1)  # eight exiled, seven of them back on the bottom
        self.assertEqual(len(t.a.exile), 0)
        self.assertEqual(sum(c.name == "Plain Aura" for c in t.a.library), 0)

    def test_it_may_decline_and_the_aura_goes_to_the_bottom_with_the_rest(self):
        library = FILLER[:3] + [AURA] + FILLER[3:10]
        t = self.cast(library, "Take none")
        self.assertEqual((len(t.a.library), len(t.a.exile), t.a.library[-1].name in {c.name for c in library[:8]}), (len(library), 0, True))

    def test_an_aura_below_the_eighth_card_is_out_of_reach(self):
        library = FILLER[:8] + [AURA, *FILLER[8:]]
        t = self.cast(library, "Plain Aura", "Bear")
        bear = next(p for p in t.a.battlefield if p.card.name == "Bear")
        self.assertEqual(t.game.power(bear), 2)

    def test_a_nonaura_enchantment_cannot_be_cast_this_way(self):
        library = FILLER[:3] + [SHRINE] + FILLER[3:10]
        t = self.cast(library, "Big Shrine")
        self.assertNotIn("Shrine", battlefield_names(t.a))

    def test_attacking_it_gets_plus_x_for_the_auras_you_control(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        herald, bear = Permanent(HERALD, sick=False), Permanent(BEAR)
        a.battlefield = [herald, bear, Permanent(AURA, attached_to=bear), Permanent(AURA_TWO, attached_to=bear)]
        game.active = 0
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual((game.power(herald), game.toughness(herald)), (4, 4))

    def test_without_auras_it_gets_nothing_and_an_opponents_aura_does_not_count(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        herald = Permanent(HERALD, sick=False)
        a.battlefield = [herald]
        b.battlefield = [Permanent(real("Quiet Aura", "{W}", "Enchantment — Aura", "Enchant creature"), attached_to=herald)]
        game.active = 0
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(game.power(herald), 2)
