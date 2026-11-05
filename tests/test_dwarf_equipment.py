"""Standard's Boros Dwarves, from their real Oracle text: equip costs that depend on the creature (Dwarven Mauler, Dragonfire Blade),
Kili the Resourceful's free equip with an enduring story (Storied) and its once-a-turn draw, Thorin attaching Equipment and then
dealing damage, The Lonely Mountain's discount per Equipment, Dain's Company and Chainsaw."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import activated_abilities
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, pick, real, run_stack, script, table3

MAULER = real("Dwarven Mauler", "{R}", "Creature — Dwarf Warrior", "Equip abilities you activate that target this creature cost {2} less to "
              "activate.", "2", "1", ("R",))
BLADE = real("Dragonfire Blade", "{1}", "Artifact — Equipment", "Equipped creature gets +2/+2 and has hexproof from monocolored.\nEquip {4}. "
             "This ability costs {1} less to activate for each color of the creature it targets.")
KILI = real("Kíli the Resourceful", "{1}{W}", "Legendary Creature — Dwarf Scout", "Storied (If you control three or more artifacts, "
            "legendaries, and/or Sagas, you have an enduring story for the rest of the game.)\nAs long as you have an enduring story, you "
            "may pay {0} rather than pay the equip cost of the first equip ability you activate each turn.\nWhenever another Dwarf or "
            "Equipment you control enters, draw a card. This ability triggers only once each turn.", "1", "2", ("W",))
THORIN = real("Thorin, Mountain-king", "{3}{R}", "Legendary Creature — Dwarf Noble", "Trample\nWhen Thorin enters, attach any number of "
              "target Equipment you control to target creature you control. When one or more Equipment become attached to that creature "
              "this way, that creature deals damage equal to its power to up to one target creature.", "3", "4", ("R",))
MOUNTAIN = real("The Lonely Mountain", "", "Land — Mountain", "({T}: Add {R}.)\nThis land enters tapped unless you control an Equipment."
                "\n{4}{R}, {T}: Create a 2/2 red Dwarf creature token. This ability costs {1} less to activate for each Equipment you "
                "control. Activate only as a sorcery.")
DAIN = real("Dáin's Company", "{R}{W}", "Creature — Dwarf Warrior", "This creature has lifelink as long as you control another Dwarf.\n"
            "When this creature enters, look at the top four cards of your library. You may reveal a Dwarf or Equipment card from among "
            "them and put it into your hand. Put the rest on the bottom of your library in a random order.", "2", "2", ("R", "W"))
CHAINSAW = real("Chainsaw", "{1}{R}", "Artifact — Equipment", "When this Equipment enters, it deals 3 damage to up to one target creature.\n"
                "Whenever one or more creatures die, put a rev counter on this Equipment.\nEquipped creature gets +X/+0, where X is the "
                "number of rev counters on this Equipment.\nEquip {3}")
MORNINGSTAR = real("Vulshok Morningstar", "{2}", "Artifact — Equipment", "Equipped creature gets +2/+2.\nEquip {2} ({2}: Attach to target "
                   "creature you control. Equip only as a sorcery.)")
BOROS = Card(name="Boros Bear", mana_cost="{R}{W}", type_line="Creature — Bear", power="2", toughness="2", colors=("R", "W"))
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.", colors=("R",))
HELIX = real("Lightning Helix", "{R}{W}", "Instant", "Lightning Helix deals 3 damage to any target and you gain 3 life.", colors=("R", "W"))
MUTATION = real("Darksteel Mutation", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature is an Insect artifact creature "
                "with base power and toughness 0/1 and has indestructible, and it loses all other abilities, card types, and creature types.")
RELIC = Card(name="Relic", type_line="Artifact", mana_cost="{1}", cmc=1.0)


def equips(game, seat, name):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + name)]


class DwarfEquipmentTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (MAULER, BLADE, KILI, THORIN, MOUNTAIN, DAIN, CHAINSAW):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_equip_costs_2_less_for_the_dwarven_mauler_only(self):
        game, _ = table3(pick("Dwarven Mauler", "Bear"))
        a = game.seats[0]
        mauler, bear, star = Permanent(MAULER), Permanent(BEAR), Permanent(MORNINGSTAR)
        a.battlefield = [mauler, bear, star]  # no mana at all
        game._perform(a, equips(game, a, "Vulshok Morningstar")[0])
        run_stack(game)
        self.assertIs(star.attached_to, mauler)
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR), Permanent(MORNINGSTAR)]
        self.assertEqual(equips(game, a, "Vulshok Morningstar"), [])  # {2}, and no mana

    def test_only_a_creature_it_can_be_paid_for_is_offered(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(options) or 0)
        a = game.seats[0]
        a.battlefield = [Permanent(MAULER), Permanent(BEAR), Permanent(MORNINGSTAR)]
        game._perform(a, equips(game, a, "Vulshok Morningstar")[0])
        self.assertTrue(all(not label.startswith("Bear") for label in asked[0]))

    def test_dragonfire_blade_costs_1_less_per_color(self):
        game, _ = table3(pick("Boros Bear"))
        a = game.seats[0]
        boros, blade = Permanent(BOROS), Permanent(BLADE)
        a.battlefield = [boros, Permanent(BEAR), blade] + lands(2)  # {2}: two colors off {4}
        game._perform(a, equips(game, a, "Dragonfire Blade")[0])
        run_stack(game)
        self.assertIs(blade.attached_to, boros)
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR), Permanent(BLADE)] + lands(2)  # a colorless Bear: {4}
        self.assertEqual(equips(game, a, "Dragonfire Blade"), [])

    def test_dragonfire_blade_gives_hexproof_from_monocolored(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear, blade = Permanent(BOROS), Permanent(BLADE)
        a.battlefield = [bear, blade]
        game.attach(blade, bear)
        b.battlefield, b.hand = lands(2), [BOLT, HELIX]
        self.assertNotIn("Boros Bear", [label.split(" ")[0] + " " + label.split(" ")[1] for label, _ in
                                        game.target_options("any", b, frozenset({"R", "monocolored", "instant"}))])
        self.assertIn(bear, [o for _, o in game.target_options("any", b, frozenset({"R", "W", "multicolored", "instant"}))])
        self.assertIn(bear, [o for _, o in game.target_options("any", a, frozenset({"R", "monocolored", "instant"}))])  # its controller's
        self.assertEqual((game.power(bear), game.toughness(bear)), (4, 4))

    def test_kili_makes_the_first_equip_each_turn_free_with_an_enduring_story(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        bear, star, star2 = Permanent(BEAR), Permanent(MORNINGSTAR), Permanent(MORNINGSTAR)
        a.battlefield = [Permanent(KILI), bear, star, star2]  # Kili (legendary) and two artifacts: three
        game._check_state()
        self.assertTrue(a.enduring_story)
        game._perform(a, equips(game, a, "Vulshok Morningstar")[0])
        run_stack(game)
        self.assertIs(star.attached_to, bear)
        self.assertEqual(equips(game, a, "Vulshok Morningstar"), [])  # the second one this turn costs {2}

    def test_no_enduring_story_with_two_and_no_free_equip(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(KILI), Permanent(BEAR), Permanent(MORNINGSTAR)]  # two
        game._check_state()
        self.assertFalse(a.enduring_story)
        self.assertEqual(equips(game, a, "Vulshok Morningstar"), [])

    def test_an_enduring_story_counts_artifacts_legendaries_and_sagas(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(KILI), Permanent(MORNINGSTAR), Permanent(Card(name="Saga", type_line="Enchantment — Saga"))]
        game._check_state()
        self.assertTrue(a.enduring_story)

    def test_no_free_equip_once_kili_is_gone_or_has_no_abilities(self):
        game, _ = table3()
        a = game.seats[0]
        a.enduring_story = True  # for the rest of the game, but the free equip is Kili's
        a.battlefield = [Permanent(BEAR), Permanent(MORNINGSTAR)]
        self.assertEqual(equips(game, a, "Vulshok Morningstar"), [])
        kili = Permanent(KILI)
        a.battlefield.append(kili)
        self.assertNotEqual(equips(game, a, "Vulshok Morningstar"), [])
        mutation = Permanent(MUTATION)
        a.battlefield.append(mutation)
        game.attach(mutation, kili)
        self.assertEqual(equips(game, a, "Vulshok Morningstar"), [])

    def test_a_mauler_without_abilities_gives_no_discount(self):
        game, _ = table3()
        a = game.seats[0]
        mauler = Permanent(MAULER)
        a.battlefield = [mauler, Permanent(MORNINGSTAR)]
        mutation = Permanent(MUTATION)
        a.battlefield.append(mutation)
        game.attach(mutation, mauler)
        self.assertEqual(equips(game, a, "Vulshok Morningstar"), [])

    def test_thorin_attaches_nothing_destroyed_in_response_and_deals_no_damage(self):
        game, _ = table3(script("Vulshok Morningstar", "Thorin", "Ogre"))
        a, b, _ = game.seats
        star = Permanent(MORNINGSTAR)
        ogre = Permanent(Card(name="Ogre", type_line="Creature — Ogre", power="3", toughness="6"))
        a.battlefield, a.hand = [star] + lands(4), [THORIN]
        b.battlefield = [ogre]
        game._perform(a, CAST + "Thorin, Mountain-king")
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()  # the Equipment and the creature are chosen
        a.battlefield.remove(star)  # destroyed in response
        run_stack(game)
        self.assertEqual((star.attached_to, ogre.damage), (None, 0))

    def test_kili_draws_once_a_turn_for_a_dwarf_or_equipment(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.library, a.hand = [Permanent(KILI)], [FOREST] * 5, []
        game._enter(a, Permanent(BEAR))  # not a Dwarf
        run_stack(game)
        self.assertEqual(len(a.hand), 0)
        game._enter(a, Permanent(MORNINGSTAR))
        game._enter(a, Permanent(MAULER))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_thorin_attaches_equipment_then_deals_damage_equal_to_power(self):
        game, _ = table3(script("Vulshok Morningstar", "Thorin", "Ogre"))  # the Equipment, the creature, then the damage
        a, b, _ = game.seats
        star = Permanent(MORNINGSTAR)
        ogre = Permanent(Card(name="Ogre", type_line="Creature — Ogre", power="3", toughness="6"))
        a.battlefield, a.hand = [star] + lands(4), [THORIN]
        b.battlefield = [ogre]
        game._perform(a, CAST + "Thorin, Mountain-king")
        run_stack(game)
        thorin = next(p for p in a.battlefield if p.card.name == "Thorin, Mountain-king")
        self.assertIs(star.attached_to, thorin)
        self.assertEqual(ogre.damage, 5)  # 3 + 2

    def test_thorin_deals_no_damage_when_nothing_was_attached(self):
        game, _ = table3(script("No target", "Thorin", "Ogre"))
        a, b, _ = game.seats
        ogre = Permanent(Card(name="Ogre", type_line="Creature — Ogre", power="3", toughness="6"))
        a.battlefield, a.hand = lands(4), [THORIN]
        b.battlefield = [ogre]
        game._perform(a, CAST + "Thorin, Mountain-king")
        run_stack(game)
        self.assertEqual(ogre.damage, 0)

    def test_the_lonely_mountain_costs_1_less_per_equipment(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(MOUNTAIN), Permanent(MORNINGSTAR), Permanent(MORNINGSTAR)] + lands(3)  # {2}{R}
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "The Lonely Mountain") and "{4}" in x))
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Dwarf" for p in a.battlefield), 1)
        self.assertTrue(activated_abilities(MOUNTAIN)[0].sorcery_speed)
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(MOUNTAIN), Permanent(MORNINGSTAR)] + lands(3)  # {3}{R}: one short
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "The Lonely Mountain") and "{4}" in x], [])

    def test_dains_company_has_lifelink_only_with_another_dwarf(self):
        game, _ = table3()
        a = game.seats[0]
        dain = Permanent(DAIN)
        a.battlefield = [dain]
        self.assertFalse(game.has_keyword(dain, "lifelink"))
        a.battlefield.append(Permanent(MAULER))
        self.assertTrue(game.has_keyword(dain, "lifelink"))

    def test_dains_company_takes_a_dwarf_or_equipment_from_the_top_four(self):
        game, _ = table3(pick("Bear", "Vulshok Morningstar"))  # a Bear would be taken if it were offered
        a = game.seats[0]
        a.battlefield, a.hand = lands(2), [DAIN]
        a.library = [BEAR, MORNINGSTAR, FOREST, FOREST, RELIC]
        game._perform(a, CAST + "Dáin's Company")
        run_stack(game)
        self.assertEqual(a.hand, [MORNINGSTAR])

    def test_chainsaw_gives_plus_one_per_rev_counter(self):
        game, _ = table3()
        a = game.seats[0]
        bear, saw = Permanent(BEAR), Permanent(CHAINSAW)
        a.battlefield = [bear, saw]
        game.attach(saw, bear)
        self.assertEqual(game.power(bear), 2)
        saw.counters["rev"] = 3
        self.assertEqual(game.power(bear), 5)


if __name__ == "__main__":
    unittest.main()
