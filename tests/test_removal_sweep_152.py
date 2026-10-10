"""The twelve removal and mass-effect spells of the precon decks that no test named (issue #152), each played from its real
Oracle text through casting, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_rules_text_81 import Table, battlefield_names, real
from tests.test_triggers_80 import BIG, FOREST, RELIC, SHRINE

WALKER = real("Walker", "{3}", "Legendary Planeswalker — Test", "")
INDESTRUCTIBLE = real("Rock", "{2}", "Creature — Golem", "Indestructible", "4", "4")
HEXPROOF = real("Veil", "{2}", "Creature — Test", "Hexproof", "2", "2")


def names(seat):
    return battlefield_names(seat)


WAVE = real("Wave of Reckoning", "{4}{W}", "Sorcery", "Each creature deals damage to itself equal to its power.")


class WaveOfReckoningTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(WAVE), [])

    def test_a_creature_dies_only_when_its_power_is_at_least_its_toughness(self):
        glass = Permanent(real("Glass", "{1}", "Creature — Test", "", "3", "2"))
        wall = Permanent(real("Wall", "{1}", "Creature — Wall", "", "0", "4"))
        brute = Permanent(real("Brute", "{3}", "Creature — Test", "", "4", "4"))
        t = Table(WAVE, mine=[glass, wall], theirs=[Permanent(OGRE), brute]).cast()
        self.assertEqual((names(t.a), names(t.b)), (["Wall"], []))

    def test_an_indestructible_creature_survives_its_own_damage(self):
        t = Table(WAVE, theirs=[Permanent(INDESTRUCTIBLE)]).cast()
        self.assertEqual(names(t.b), ["Rock"])

    def test_noncreature_permanents_are_unharmed(self):
        t = Table(WAVE, theirs=[Permanent(RELIC), Permanent(WALKER)]).cast()
        self.assertEqual(names(t.b), ["Relic", "Walker"])


WINDS = real("Winds of Rath", "{3}{W}{W}", "Sorcery", "Destroy all creatures that aren't enchanted. They can't be regenerated.")
WARD = real("Ward", "{1}", "Enchantment — Aura", "Enchant creature")


class WindsOfRathTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(WINDS), [])

    def test_enchanted_creatures_survive_and_the_rest_die(self):
        warded = Permanent(BEAR)
        aura = Permanent(WARD, attached_to=warded)
        t = Table(WINDS, mine=[warded, aura, Permanent(OGRE)], theirs=[Permanent(BEAR)]).cast()
        self.assertEqual((names(t.a), names(t.b)), (["Bear", "Ward"], []))

    def test_an_aura_of_the_opponent_on_my_creature_also_protects_it(self):
        mine = Permanent(BEAR)
        t = Table(WINDS, mine=[mine])
        t.b.battlefield = [Permanent(WARD, attached_to=mine)]
        t.cast()
        self.assertEqual(names(t.a), ["Bear"])

    def test_an_indestructible_creature_is_unaffected_either_way(self):
        t = Table(WINDS, theirs=[Permanent(INDESTRUCTIBLE)]).cast()
        self.assertEqual(names(t.b), ["Rock"])


CULLING = real("Culling Ritual", "{2}{B}{G}", "Sorcery", "Destroy each nonland permanent with mana value 2 or less. Add {B} or {G} for each "
                                                       "permanent destroyed this way.")


class CullingRitualTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(CULLING), [])

    def test_it_destroys_cheap_nonland_permanents_on_every_side_and_adds_mana_for_each(self):
        t = Table(CULLING, "Pass", mine=[Permanent(RELIC), Permanent(SHRINE), Permanent(BIG)], theirs=[Permanent(RELIC), Permanent(FOREST)])
        t.cast()
        self.assertEqual((names(t.a), names(t.b)), (["Big"], ["Forest"]))
        self.assertEqual(len(t.a.mana_pool), 3)
        self.assertTrue(all(mana == frozenset("BG") for mana in t.a.mana_pool))  # each is {B} or {G}, chosen when spent

    def test_it_adds_nothing_when_nothing_is_destroyed(self):
        t = Table(CULLING, "Pass", mine=[Permanent(BIG)]).cast()
        self.assertEqual((names(t.a), len(t.a.mana_pool)), (["Big"], 0))

    def test_an_indestructible_permanent_gives_no_mana(self):
        cheap_rock = Permanent(real("Cheap Rock", "{1}", "Creature — Golem", "Indestructible", "1", "1"))
        t = Table(CULLING, "Pass", mine=[cheap_rock]).cast()
        self.assertEqual((names(t.a), len(t.a.mana_pool)), (["Cheap Rock"], 0))


CASUALTIES = real("Casualties of War", "{2}{B}{B}{G}{G}", "Sorcery",
                  "Choose one or more —\n• Destroy target artifact.\n• Destroy target creature.\n• Destroy target enchantment.\n• Destroy "
                  "target land.\n• Destroy target planeswalker.")


class CasualtiesOfWarTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(CASUALTIES), [])

    def test_all_five_modes_destroy_one_permanent_each(self):
        theirs = [Permanent(RELIC), Permanent(OGRE), Permanent(SHRINE), Permanent(FOREST), Permanent(WALKER), Permanent(BEAR)]
        t = Table(CASUALTIES, "Destroy target artifact", "Destroy target creature", "Destroy target enchantment", "Destroy target land",
                  "Destroy target planeswalker", "Relic", "Ogre", "Shrine", "Forest", "Walker", n=8, theirs=theirs).cast()
        self.assertEqual(names(t.b), ["Bear"])

    def test_one_mode_alone_leaves_everything_else(self):
        theirs = [Permanent(RELIC), Permanent(OGRE), Permanent(SHRINE)]
        t = Table(CASUALTIES, "Destroy target creature", "Done", "Ogre", n=8, theirs=theirs).cast()
        self.assertEqual(names(t.b), ["Relic", "Shrine"])

    def test_it_hits_my_own_permanents_when_nothing_else_can_be_chosen(self):
        t = Table(CASUALTIES, "Destroy target creature", "Done", "Bear", n=8, mine=[Permanent(BEAR)])
        t.cast()
        self.assertEqual(names(t.a), [])


RIP_APART = real("Rip Apart", "{R}{W}", "Sorcery", "Choose one —\n• Rip Apart deals 3 damage to target creature or planeswalker.\n• Destroy "
                                                     "target artifact or enchantment.")


class RipApartTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(RIP_APART), [])

    def test_three_damage_kills_a_creature(self):
        t = Table(RIP_APART, "Rip Apart deals", "Ogre", theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(names(t.b), [])

    def test_three_damage_does_not_kill_a_bigger_creature(self):
        t = Table(RIP_APART, "Rip Apart deals", "Brute", theirs=[Permanent(real("Brute", "{4}", "Creature — Test", "", "4", "4"))]).cast()
        self.assertEqual(names(t.b), ["Brute"])

    def test_three_damage_takes_loyalty_off_a_planeswalker(self):
        walker = Permanent(WALKER, loyalty=5)
        t = Table(RIP_APART, "Rip Apart deals", "Walker", theirs=[walker]).cast()
        self.assertEqual(walker.loyalty, 2)

    def test_destroy_an_artifact_or_an_enchantment(self):
        for victim in (RELIC, SHRINE):
            t = Table(RIP_APART, "Destroy target artifact", "Destroy", victim.name, theirs=[Permanent(victim), Permanent(OGRE)]).cast()
            self.assertEqual(names(t.b), ["Ogre"], victim.name)

    def test_the_destroy_mode_is_not_offered_with_only_creatures_around(self):
        t = Table(RIP_APART, theirs=[Permanent(OGRE)])
        t.cast()
        [(prompt, modes)] = [p for p in t.a.player.prompts if p[0].startswith("Choose a mode")]
        self.assertEqual(modes, ["Rip Apart deals 3 damage to target creature or planeswalker."])


ABRADE = real("Abrade", "{1}{R}", "Instant", "Choose one —\n• Abrade deals 3 damage to target creature.\n• Destroy target artifact.")


class AbradeTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(ABRADE), [])

    def test_three_damage_to_a_creature(self):
        t = Table(ABRADE, "Abrade deals", "Ogre", theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(names(t.b), [])

    def test_it_cannot_damage_a_planeswalker(self):
        walker = Permanent(WALKER, loyalty=5)
        t = Table(ABRADE, "Abrade deals", "Walker", theirs=[walker])
        t.cast()
        self.assertEqual(walker.loyalty, 5)

    def test_destroy_an_artifact_but_not_an_enchantment(self):
        t = Table(ABRADE, "Destroy target artifact", "Relic", theirs=[Permanent(RELIC), Permanent(SHRINE)]).cast()
        self.assertEqual(names(t.b), ["Shrine"])


GRASP = real("Infernal Grasp", "{1}{B}", "Instant", "Destroy target creature. You lose 2 life.")


class InfernalGraspTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(GRASP), [])

    def test_it_destroys_the_creature_and_costs_two_life(self):
        t = Table(GRASP, "Ogre", theirs=[Permanent(OGRE)]).cast()
        self.assertEqual((names(t.b), t.a.life), ([], 38))

    def test_an_indestructible_creature_survives_but_the_life_is_still_lost(self):
        t = Table(GRASP, "Rock", theirs=[Permanent(INDESTRUCTIBLE)]).cast()
        self.assertEqual((names(t.b), t.a.life), (["Rock"], 38))

    def test_a_hexproof_creature_is_not_a_target(self):
        t = Table(GRASP, "Veil", theirs=[Permanent(HEXPROOF)])
        self.assertFalse(any(a.startswith(CAST + "Infernal Grasp") for a in t.game.legal_actions(t.a)))


UNMAKING = real("Anguished Unmaking", "{1}{W}{B}", "Instant", "Exile target nonland permanent. You lose 3 life.")


class AnguishedUnmakingTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(UNMAKING), [])

    def test_it_exiles_any_nonland_permanent_and_costs_three_life(self):
        for victim in (OGRE, RELIC, SHRINE, WALKER):
            t = Table(UNMAKING, victim.name, theirs=[Permanent(victim)]).cast()
            self.assertEqual((names(t.b), t.a.life), ([], 37), victim.name)
            self.assertIn(victim.name, [c.name for c in t.b.exile])

    def test_exile_gets_past_indestructible(self):
        t = Table(UNMAKING, "Rock", theirs=[Permanent(INDESTRUCTIBLE)]).cast()
        self.assertEqual(names(t.b), [])

    def test_a_land_is_not_a_target(self):
        t = Table(UNMAKING, "Forest", theirs=[Permanent(FOREST)])
        self.assertFalse(any(a.startswith(CAST + "Anguished Unmaking") for a in t.game.legal_actions(t.a)))


FRACTURE = real("Fracture", "{W}{B}", "Instant", "Destroy target artifact, enchantment, or planeswalker.")


class FractureTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(FRACTURE), [])

    def test_it_destroys_an_artifact_an_enchantment_or_a_planeswalker(self):
        for victim in (RELIC, SHRINE, WALKER):
            t = Table(FRACTURE, victim.name, theirs=[Permanent(victim)]).cast()
            self.assertEqual(names(t.b), [], victim.name)

    def test_a_creature_is_not_a_target(self):
        t = Table(FRACTURE, "Ogre", theirs=[Permanent(OGRE)])
        self.assertFalse(any(a.startswith(CAST + "Fracture") for a in t.game.legal_actions(t.a)))


SALVO = real("Volcanic Salvo", "{10}{R}{R}", "Sorcery", "This spell costs {X} less to cast, where X is the total power of creatures you control.\n"
                                                         "Volcanic Salvo deals 6 damage to each of up to two target creatures and/or planeswalkers.")


class VolcanicSalvoTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SALVO), [])

    def castable(self, power_in_play, n):
        mine = [Permanent(real(f"P{i}", "{1}", "Creature — Test", "", "1", "1")) for i in range(power_in_play)]
        t = Table(SALVO, n=n, mine=mine, theirs=[Permanent(OGRE)])
        return any(a.startswith(CAST + "Volcanic Salvo") for a in t.game.legal_actions(t.a))

    def test_it_costs_less_by_the_total_power_of_your_creatures(self):
        self.assertTrue(self.castable(10, 2))   # {R}{R}
        self.assertFalse(self.castable(9, 2))   # needs three
        self.assertTrue(self.castable(9, 3))

    def test_it_is_the_total_power_and_not_the_number_of_creatures(self):
        t = Table(SALVO, n=4, mine=[Permanent(OGRE), Permanent(BIG)], theirs=[Permanent(OGRE)])  # power 3 + 5, so {2}{R}{R}
        self.assertTrue(any(a.startswith(CAST + "Volcanic Salvo") for a in t.game.legal_actions(t.a)))
        t = Table(SALVO, n=3, mine=[Permanent(OGRE), Permanent(BIG)], theirs=[Permanent(OGRE)])
        self.assertFalse(any(a.startswith(CAST + "Volcanic Salvo") for a in t.game.legal_actions(t.a)))

    def test_the_reduction_never_goes_below_the_colored_mana(self):
        self.assertFalse(self.castable(20, 1))

    def test_six_damage_to_each_of_up_to_two_creatures_or_planeswalkers(self):
        mine = [Permanent(real(f"P{i}", "{1}", "Creature — Test", "", "1", "1")) for i in range(10)]
        theirs = [Permanent(OGRE), Permanent(WALKER, loyalty=6), Permanent(BEAR)]
        t = Table(SALVO, "Ogre", "Walker", n=2, mine=mine, theirs=theirs).cast()
        self.assertEqual(names(t.b), ["Bear"])

    def test_the_second_target_may_be_left_out(self):
        mine = [Permanent(real(f"P{i}", "{1}", "Creature — Test", "", "1", "1")) for i in range(10)]
        t = Table(SALVO, "Ogre", "No target", n=2, mine=mine, theirs=[Permanent(OGRE), Permanent(BEAR)]).cast()
        self.assertEqual(names(t.b), ["Bear"])


TORRENT = real("Volcanic Torrent", "{4}{R}", "Sorcery",
               "Cascade (When you cast this spell, exile cards from the top of your library until you exile a nonland card that costs "
               "less. You may cast it without paying its mana cost. Put the exiled cards on the bottom in a random order.)\nVolcanic "
               "Torrent deals X damage to each creature and planeswalker your opponents control, where X is the number of spells you've "
               "cast this turn.")


class VolcanicTorrentTests(unittest.TestCase):
    def cast(self, library, mine=(), theirs=(), choose="Yes"):
        t = Table(TORRENT, library=library, mine=mine, theirs=theirs, policy=pick(choose))
        return t.cast()

    def test_parse(self):
        self.assertEqual(unsupported_lines(TORRENT), [])

    def test_with_nothing_to_cascade_into_it_counts_only_itself(self):
        walker = Permanent(WALKER, loyalty=5)
        t = self.cast([FOREST] * 5, theirs=[walker, Permanent(real("Tough", "{3}", "Creature — Test", "", "2", "3"))])
        self.assertEqual((walker.loyalty, t.b.battlefield[1].damage if len(t.b.battlefield) > 1 else None), (4, 1))

    def test_the_cascaded_spell_counts_too(self):
        cheap = real("Cheap Spell", "{1}", "Sorcery", "You gain 1 life.")
        tough = Permanent(real("Tough", "{3}", "Creature — Test", "", "2", "3"))
        t = self.cast([FOREST, cheap, FOREST], theirs=[tough])
        self.assertEqual(tough.damage, 2)  # Torrent and the free Cheap Spell

    def test_it_leaves_my_creatures_and_noncreature_permanents_alone(self):
        mine = Permanent(BEAR)
        t = self.cast([FOREST] * 5, mine=[mine], theirs=[Permanent(RELIC)])
        self.assertEqual((mine.damage, names(t.b)), (0, ["Relic"]))

    def test_it_kills_what_it_damages_enough(self):
        t = self.cast([FOREST] * 5, theirs=[Permanent(real("Little", "{1}", "Creature — Test", "", "1", "1"))])
        self.assertEqual(names(t.b), [])


SPEAR = real("Mortality Spear", "{2}{B}{G}", "Instant", "This spell costs {2} less to cast if you gained life this turn.\nDestroy target nonland permanent.")


class MortalitySpearTests(unittest.TestCase):
    def castable(self, n, gained=None):
        t = Table(SPEAR, n=n, theirs=[Permanent(OGRE)])
        if gained is not None:
            t.game.change_life(t.a, gained)
        return any(a.startswith(CAST + "Mortality Spear") for a in t.game.legal_actions(t.a))

    def test_parse(self):
        self.assertEqual(unsupported_lines(SPEAR), [])

    def test_two_lands_are_enough_after_gaining_life(self):
        self.assertTrue(self.castable(2, gained=1))

    def test_two_lands_are_not_enough_otherwise(self):
        self.assertFalse(self.castable(2))
        self.assertFalse(self.castable(2, gained=-1))

    def test_four_lands_always_pay(self):
        self.assertTrue(self.castable(4))

    def test_it_destroys_a_nonland_permanent_and_not_a_land(self):
        t = Table(SPEAR, "Ogre", n=2, theirs=[Permanent(OGRE), Permanent(FOREST)])
        t.game.change_life(t.a, 1)
        t.cast()
        self.assertEqual(names(t.b), ["Forest"])
        t = Table(SPEAR, "Forest", n=4, theirs=[Permanent(FOREST)])
        self.assertFalse(any(a.startswith(CAST + "Mortality Spear") for a in t.game.legal_actions(t.a)))
