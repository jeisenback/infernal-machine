"""The fourth popularity pass: keyword abilities known by their rules text (Outlast, Fabricate, Soulshift, Modular, Evolve,
Mentor, Mobilize, Bloodthirst, Renown, Transmute, Dredge, Umbra armor) and Auras that enchant a Forest or Mountain, and so on."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import aura_kind, dredge_of, enters_with_counters
from infernal_machine.game import ACTIVATE, ACTIVATE_HAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, real, run_stack, script, table3

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))

FALCONER = real("Abzan Falconer", "{2}{W}", "Creature — Human Soldier", "Outlast {W} ({W}, {T}: Put a +1/+1 counter on this creature. "
                "Outlast only as a sorcery.)\nEach creature you control with a +1/+1 counter on it has flying.", "2", "3")
ANGEL = real("Angel of Invention", "{3}{W}{W}", "Creature — Angel", "Fabricate 2 (When this creature enters, put two +1/+1 counters on it or "
             "create two 1/1 colorless Servo artifact creature tokens.)\nFlying, vigilance, lifelink", "2", "1")
SOULSHIFTER = real("Spirit Hunter", "{3}{G}", "Creature — Human Monk", "Soulshift 3 (When this creature dies, you may return target Spirit card "
                   "with mana value 3 or less from your graveyard to your hand.)", "3", "3")
SPIRIT = real("Little Spirit", "{1}{W}", "Creature — Spirit", "", "1", "1")
BIG_SPIRIT = real("Big Spirit", "{4}{W}", "Creature — Spirit", "", "4", "4")
RAVAGER = real("Arcbound Ravager", "{1}", "Artifact Creature — Beast", "Sacrifice an artifact: Put a +1/+1 counter on this creature.\nModular 1 "
               "(This creature enters with a +1/+1 counter on it. When it dies, you may put its +1/+1 counters on target artifact creature.)", "0", "0")
BLOOD_OGRE = real("Blood Ogre", "{2}{R}", "Creature — Ogre Warrior", "Bloodthirst 1 (If an opponent was dealt damage this turn, this creature "
                  "enters with a +1/+1 counter on it.)\nFirst strike", "2", "2")
SERGEANT = real("Akroan Sergeant", "{1}{R}", "Creature — Human Warrior", "First strike\nRenown 1 (When this creature deals combat damage to a "
                "player, if it isn't renowned, put a +1/+1 counter on it and it becomes renowned.)", "2", "1")
SNAPJAW = real("Adaptive Snapjaw", "{6}{U}", "Creature — Lizard Beast", "Evolve (Whenever a creature you control enters, if that creature has "
               "greater power or toughness than this creature, put a +1/+1 counter on this creature.)", "6", "2")
MENTOR = real("Barging Sergeant", "{1}{R}", "Creature — Human Warrior", "Haste\nMentor (Whenever this creature attacks, put a +1/+1 counter on "
              "target attacking creature with lesser power.)", "3", "2")
MOBILIZER = real("Shock Brigade", "{1}{R}", "Creature — Human Warrior", "Mobilize 1 (Whenever this creature attacks, create a tapped and attacking "
                 "1/1 red Warrior creature token. Sacrifice it at the beginning of the next end step.)", "2", "2")
TRANSMUTER = real("Dimir House Guard", "{3}{B}", "Creature — Skeleton", "Fear\nTransmute {1}{B}{B} ({1}{B}{B}, Discard this card: Search your library "
                  "for a card with the same mana value as this card, reveal it, put it into your hand, then shuffle. Transmute only as a sorcery.)", "2", "3")
FOUR_DROP = real("Four Drop", "{2}{R}{R}", "Creature — Ogre", "", "4", "4")
ONE_DROP = real("One Drop", "{R}", "Creature — Ogre", "", "1", "1")
BOAR_UMBRA = real("Boar Umbra", "{2}{G}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +3/+3.\nUmbra armor (If enchanted creature "
                  "would be destroyed, instead remove all damage from it and destroy this Aura.)")
LOAM = real("Life from the Loam", "{1}{G}", "Sorcery", "Return up to three target land cards from your graveyard to your hand.\nDredge 3 "
            "(If you would draw a card, you may mill three cards instead. If you do, return this card from your graveyard to your hand.)")
SPRAWL = real("Utopia Sprawl", "{G}", "Enchantment — Aura", "Enchant Forest\nAs this Aura enters, choose a color.\nWhenever enchanted Forest is tapped "
              "for mana, its controller adds an additional one mana of the chosen color.")
MOUNTAIN_AURA = real("Awaken", "{1}{R}", "Enchantment — Aura", "Enchant Mountain\nEnchanted Mountain has haste.")
MURDER = real("Murder", "{1}{B}{B}", "Instant", "Destroy target creature.")
WORLD_TREE = real("Deadly Deed", "{2}{B}{B}", "Sorcery", "Destroy all creatures.")

CREATURES = (FALCONER, ANGEL, SOULSHIFTER, RAVAGER, BLOOD_OGRE, SERGEANT, SNAPJAW, MENTOR, MOBILIZER, TRANSMUTER, LOAM, BOAR_UMBRA, SPRAWL)


def table(*cards, policy=None, mana=0):
    game, _ = table3(policy or script("Pass"))
    a = game.seats[0]
    a.hand, a.library, a.graveyard = [], [FOREST] * 8, []
    a.battlefield = lands(mana) + [Permanent(c, sick=False) for c in cards]
    return game, a


def on_battlefield(seat, card):
    return next(p for p in seat.battlefield if p.card is card)


def counters(permanent):
    return permanent.counters.get("+1/+1", 0)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CREATURES:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_aura_can_enchant_a_forest_or_a_creature_of_a_kind(self):
        self.assertEqual(aura_kind(SPRAWL), "forest")
        self.assertEqual(aura_kind(MOUNTAIN_AURA), "mountain")
        text = "Enchant artifact or creature you control"
        self.assertEqual(aura_kind(real("Some Aura", "{1}", "Enchantment — Aura", text)), "artifact or creature you control")
        self.assertEqual(aura_kind(real("Some Aura", "{1}", "Enchantment — Aura", "Enchant nonblack creature")), "nonblack creature")
        self.assertEqual(aura_kind(real("Some Aura", "{1}", "Enchantment — Aura", "Enchant Equipment")), "equipment")

    def test_an_aura_for_players_is_left_alone(self):
        self.assertIsNone(aura_kind(real("Curse", "{1}", "Enchantment — Aura Curse", "Enchant player")))


class OutlastTests(unittest.TestCase):
    def test_outlast_puts_a_counter_on_it_at_sorcery_speed(self):
        game, a = table(FALCONER, mana=1)
        label = next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE))
        game._perform(a, label)
        run_stack(game)
        falconer = on_battlefield(a, FALCONER)
        self.assertEqual(counters(falconer), 1)
        self.assertTrue(falconer.tapped)

    def test_it_is_not_offered_at_instant_speed(self):
        game, a = table(FALCONER, mana=1)
        game.step = "combat"
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)])


class FabricateTests(unittest.TestCase):
    def enter(self, answer):
        game, a = table(policy=script(answer))
        game._enter(a, Permanent(ANGEL, sick=False))
        run_stack(game)
        return a

    def test_counters_mode(self):
        a = self.enter("Put two")
        self.assertEqual(counters(on_battlefield(a, ANGEL)), 2)
        self.assertEqual([p for p in a.battlefield if p.card.name == "Servo"], [])

    def test_servo_mode(self):
        a = self.enter("Create two")
        self.assertEqual(counters(on_battlefield(a, ANGEL)), 0)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Servo"]), 2)


class SoulshiftTests(unittest.TestCase):
    def test_it_returns_a_small_spirit(self):
        game, a = table(SOULSHIFTER)
        a.graveyard = [SPIRIT, BIG_SPIRIT]
        game.destroy(on_battlefield(a, SOULSHIFTER))
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Little Spirit"])

    def test_a_spirit_that_is_too_big_stays(self):
        game, a = table(SOULSHIFTER)
        a.graveyard = [BIG_SPIRIT]
        game.destroy(on_battlefield(a, SOULSHIFTER))
        run_stack(game)
        self.assertEqual(a.hand, [])


class ModularTests(unittest.TestCase):
    def test_it_enters_with_a_counter(self):
        self.assertEqual(enters_with_counters(RAVAGER), {"+1/+1": 1})

    def test_its_counters_move_to_an_artifact_creature_when_it_dies(self):
        game, a = table()
        a.battlefield.append(Permanent(RAVAGER, sick=False, counters={"+1/+1": 3}))
        other = Permanent(real("Myr", "{2}", "Artifact Creature — Myr", "", "1", "1"), sick=False)
        a.battlefield.append(other)
        game.destroy(on_battlefield(a, RAVAGER))
        run_stack(game)
        self.assertEqual(counters(other), 3)


class BloodthirstTests(unittest.TestCase):
    def test_without_damage_to_an_opponent_it_enters_plain(self):
        self.assertEqual(enters_with_counters(BLOOD_OGRE), {})

    def test_with_it_the_ogre_enters_with_a_counter(self):
        self.assertEqual(enters_with_counters(BLOOD_OGRE, bloodthirsty=True), {"+1/+1": 1})

    def test_the_game_asks_whether_an_opponent_was_dealt_damage(self):
        game, a = table()
        game._enter(a, Permanent(BLOOD_OGRE))
        self.assertEqual(counters(on_battlefield(a, BLOOD_OGRE)), 0)
        game.damage(game.seats[1], 1)
        late = real("Blood Wurm", "{3}{B}", "Creature — Wurm", BLOOD_OGRE.oracle_text, "3", "3")
        game._enter(a, Permanent(late))
        self.assertEqual(counters(on_battlefield(a, late)), 1)

    def test_damage_to_yourself_does_not_count(self):
        game, a = table()
        game.damage(a, 1)
        game._enter(a, Permanent(BLOOD_OGRE))
        self.assertEqual(counters(on_battlefield(a, BLOOD_OGRE)), 0)


def attack(attackers, blockers=(), policy=None):
    """Combat in which seat A attacks with everything and B never blocks; the triggers resolve afterwards."""
    from tests.helpers import attack_all
    game, _ = table3(attack_all)
    a, b = game.seats[:2]
    a.battlefield = [c if isinstance(c, Permanent) else Permanent(c, sick=False) for c in attackers]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    run_stack(game)
    game.combat.declare_blockers()
    if game.combat.has_first_strike():
        game.combat.deal_damage(first_strike_step=True)
        game._check_state()
    game.combat.deal_damage(first_strike_step=False)
    game._check_state()
    run_stack(game)
    return game, a, b


class RenownTests(unittest.TestCase):
    def test_it_gets_its_counter_once(self):
        game, a, b = attack([SERGEANT])
        sergeant = on_battlefield(a, SERGEANT)
        self.assertEqual(counters(sergeant), 1)
        self.assertTrue(sergeant.renowned)

    def test_a_renowned_creature_gets_no_more(self):
        sergeant = Permanent(SERGEANT, sick=False, renowned=True)
        game, a, b = attack([sergeant])
        self.assertEqual(counters(sergeant), 0)
        self.assertGreater(b.damage_taken, 0)


SMALL = real("Small", "{1}", "Creature — Bear", "", "1", "1")
TOUGH = real("Tough", "{2}", "Creature — Bear", "", "1", "3")
STRONG = real("Strong", "{3}", "Creature — Bear", "", "7", "1")


class EvolveTests(unittest.TestCase):
    def evolved(self, entering):
        game, a = table(SNAPJAW)
        game._enter(a, Permanent(entering))
        run_stack(game)
        return counters(on_battlefield(a, SNAPJAW))

    def test_a_creature_with_more_toughness_evolves_it(self):
        self.assertEqual(self.evolved(TOUGH), 1)

    def test_a_creature_with_more_power_evolves_it(self):
        self.assertEqual(self.evolved(STRONG), 1)

    def test_a_creature_that_is_no_greater_does_not(self):
        self.assertEqual(self.evolved(SMALL), 0)

    def test_the_creature_itself_entering_does_not(self):
        game, a = table()
        game._enter(a, Permanent(SNAPJAW))
        run_stack(game)
        self.assertEqual(counters(on_battlefield(a, SNAPJAW)), 0)


class MentorTests(unittest.TestCase):
    def test_the_counter_goes_to_an_attacker_with_lesser_power(self):
        game, a, b = attack([MENTOR, ONE_DROP, FOUR_DROP])
        self.assertEqual([counters(on_battlefield(a, c)) for c in (MENTOR, ONE_DROP, FOUR_DROP)], [0, 1, 0])

    def test_an_attacker_with_equal_power_is_not_a_target(self):
        twin = real("Twin", "{1}", "Creature — Bear", "", "3", "3")
        game, a, b = attack([MENTOR, twin])
        self.assertEqual(counters(on_battlefield(a, twin)), 0)
        self.assertEqual(counters(on_battlefield(a, MENTOR)), 0)

    def test_a_creature_that_does_not_attack_is_not_a_target(self):
        game, a = table(MENTOR, ONE_DROP)
        game.step = "combat"
        game.combat.attacks = []
        self.assertEqual(game.target_options("attacking creature with lesser power", a), [])


class MobilizeTests(unittest.TestCase):
    def test_a_warrior_joins_the_attack_tapped(self):
        game, a, b = attack([MOBILIZER])
        [warrior] = [p for p in a.battlefield if p.card.name == "Warrior"]
        self.assertTrue(warrior.tapped)
        self.assertIn(warrior, [x.attacker for x in game.combat.attacks])
        self.assertEqual(b.damage_taken, 3)

    def test_it_is_sacrificed_as_the_turn_ends(self):
        game, a, b = attack([MOBILIZER])
        [(turn, sacrifice)] = game.at_end_step
        sacrifice()
        self.assertEqual([p for p in a.battlefield if p.card.name == "Warrior"], [])

    def test_the_warriors_do_not_trigger_mobilize_again(self):
        game, a, b = attack([MOBILIZER])
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Warrior"]), 1)


class TransmuteTests(unittest.TestCase):
    def test_it_finds_a_card_with_the_same_mana_value(self):
        offered = []
        game, a = table(mana=3, policy=lambda prompt, options: offered.append(options) or 0)
        a.hand = [TRANSMUTER]
        a.library = [ONE_DROP, FOUR_DROP, BEAR, FOREST]
        label = next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE_HAND))
        game._perform(a, label)
        run_stack(game)
        self.assertEqual(offered[-1], ["Four Drop"])
        self.assertEqual(sorted(c.name for c in a.hand), ["Four Drop"])
        self.assertEqual([c.name for c in a.graveyard], ["Dimir House Guard"])

    def test_it_needs_a_main_phase(self):
        game, a = table(mana=3)
        a.hand = [TRANSMUTER]
        game.step = "combat"
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(ACTIVATE_HAND)])

    def test_a_land_looks_for_mana_value_zero(self):
        land = real("Tolaria West", "", "Land", "{T}: Add {U}.\nTransmute {1}{U}{U} ({1}{U}{U}, Discard this card: Search your library for a "
                    "card with mana value 0, reveal it, put it into your hand, then shuffle. Transmute only as a sorcery.)")
        game, a = table(mana=3, policy=script("Island"))
        a.hand = [land]
        a.library = [ONE_DROP, ISLAND]
        label = next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE_HAND))
        game._perform(a, label)
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Island"])


class UmbraArmorTests(unittest.TestCase):
    def armored(self):
        game, a = table(OGRE)
        ogre = on_battlefield(a, OGRE)
        a.battlefield.append(Permanent(BOAR_UMBRA, attached_to=ogre))
        return game, a, ogre

    def test_a_destroy_effect_destroys_the_aura_instead(self):
        game, a, ogre = self.armored()
        game.destroy(ogre)
        self.assertIn(ogre, a.battlefield)
        self.assertEqual([c.name for c in a.graveyard], ["Boar Umbra"])

    def test_it_works_even_when_regeneration_is_not_allowed(self):
        game, a, ogre = self.armored()
        game.destroy(ogre, no_regen=True)
        self.assertIn(ogre, a.battlefield)

    def test_lethal_damage_is_removed(self):
        game, a, ogre = self.armored()
        ogre.damage = 6
        game._check_state()
        self.assertIn(ogre, a.battlefield)
        self.assertEqual(ogre.damage, 0)
        self.assertEqual([c.name for c in a.graveyard], ["Boar Umbra"])

    def test_a_wrath_is_survived_once(self):
        game, a, ogre = self.armored()
        game.destroy_all([ogre])
        self.assertIn(ogre, a.battlefield)

    def test_sacrifice_is_not_prevented(self):
        game, a, ogre = self.armored()
        game.sacrifice(a, "creature")
        self.assertNotIn(ogre, a.battlefield)

    def test_a_second_destruction_kills_it(self):
        game, a, ogre = self.armored()
        game.destroy(ogre)
        game.destroy(ogre)
        self.assertNotIn(ogre, a.battlefield)


class DredgeTests(unittest.TestCase):
    def test_the_dredge_number_is_read(self):
        self.assertEqual(dredge_of(LOAM), 3)
        self.assertIsNone(dredge_of(SMALL))

    def test_dredge_replaces_a_draw(self):
        game, a = table(policy=script("Dredge"))
        a.graveyard = [LOAM]
        a.library = [FOREST, ISLAND, BEAR, OGRE, FOUR_DROP]
        game.draw(a, 1)
        self.assertEqual([c.name for c in a.hand], ["Life from the Loam"])
        self.assertEqual(len(a.library), 2)
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Forest", "Island"])

    def test_the_player_may_draw_instead(self):
        game, a = table(policy=script("Draw"))
        a.graveyard = [LOAM]
        a.library = [FOREST] * 5
        game.draw(a, 1)
        self.assertEqual([c.name for c in a.hand], ["Forest"])
        self.assertEqual([c.name for c in a.graveyard], ["Life from the Loam"])

    def test_it_needs_enough_cards_in_the_library(self):
        game, a = table(policy=script("Dredge"))
        a.graveyard = [LOAM]
        a.library = [FOREST, ISLAND]
        game.draw(a, 1)
        self.assertEqual([c.name for c in a.hand], ["Forest"])


class AuraKindTests(unittest.TestCase):
    def test_utopia_sprawl_can_only_go_on_a_forest(self):
        game, a = table(OGRE, mana=0)
        a.battlefield += [Permanent(FOREST), Permanent(ISLAND)]
        names = [label for label, _ in game.target_options(aura_kind(SPRAWL), a)]
        self.assertEqual(len(names), 1)
        self.assertIn("Forest", names[0])

    def test_the_enchanted_forest_makes_an_extra_mana_of_the_chosen_color(self):
        game, a = table(policy=script("Pass"))
        forest = Permanent(FOREST)
        a.battlefield.append(forest)
        a.battlefield.append(Permanent(SPRAWL, attached_to=forest, chosen_color="R"))
        sources = [m for m in game._mana_sources(a) if m.permanent is forest]
        self.assertEqual(sorted("".join(sorted(m.types)) for m in sources), ["G", "R"])


if __name__ == "__main__":
    unittest.main()
