"""The Pauper decks one card short (#645), from the cards' real Oracle text: Deem Inferior (cheaper for each card drawn this turn; the
owner puts the permanent second from the top or on the bottom), Sleep of the Dead (it doesn't untap during its controller's next untap
step), Benevolent Blessing (protection that spares its controller's attachments), Extract a Confession (the greatest power if evidence was
collected), Reckoner's Bargain and Fling (what an additional cost sacrificed) and Melded Moxite (a tapped token)."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.game import CAST, EVIDENCE_NONE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, OGRE, activate, lands, pick, real, run_stack, script, table3

DEEM = real("Deem Inferior", "{3}{U}", "Sorcery", "This spell costs {1} less to cast for each card you've drawn this turn.\nThe owner of target "
            "nonland permanent puts it into their library second from the top or on the bottom.", colors=("U",))
SLEEP = real("Sleep of the Dead", "{U}", "Sorcery", "Tap target creature. It doesn't untap during its controller's next untap step.\nEscape—"
             "{2}{U}, Exile three other cards from your graveyard. (You may cast this card from your graveyard for its escape cost.)", colors=("U",))
BLESSING = real("Benevolent Blessing", "{1}{W}", "Enchantment — Aura", "Flash\nEnchant creature\nAs this Aura enters, choose a color.\n"
                "Enchanted creature has protection from the chosen color. This effect doesn't remove Auras and Equipment you control that are "
                "already attached to it.", colors=("W",))
CONFESSION = real("Extract a Confession", "{1}{B}", "Sorcery", "As an additional cost to cast this spell, you may collect evidence 6. (Exile "
                  "cards with total mana value 6 or greater from your graveyard.)\nEach opponent sacrifices a creature of their choice. If "
                  "evidence was collected, instead each opponent sacrifices a creature with the greatest power among creatures they control.",
                  colors=("B",))
BARGAIN = real("Reckoner's Bargain", "{1}{B}", "Instant", "As an additional cost to cast this spell, sacrifice an artifact or creature.\nYou "
               "gain life equal to the sacrificed permanent's mana value. Draw two cards.", colors=("B",))
FLING = real("Fling", "{1}{R}", "Instant", "As an additional cost to cast this spell, sacrifice a creature.\nFling deals damage equal to the "
             "sacrificed creature's power to any target.", colors=("R",))
MOXITE = real("Melded Moxite", "{1}{R}", "Artifact", "When this artifact enters, you may discard a card. If you do, draw two cards.\n{3}, "
              "Sacrifice this artifact: Create a tapped 2/2 colorless Robot artifact creature token.", colors=("R",))
RED_AURA = real("Red Aura", "{R}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+1.", colors=("R",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


class PauperNearCompleteTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DEEM, SLEEP, BLESSING, CONFESSION, BARGAIN, FLING, MOXITE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_deem_inferior_costs_less_for_each_card_drawn_and_its_owner_picks_the_place(self):
        game, _ = table3(None, pick("On the bottom"))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.library = lands(2, ISLAND), [DEEM], [ISLAND] * 3
        bear = Permanent(BEAR)
        b.battlefield, b.library = [bear], [OGRE, OGRE, OGRE]
        self.assertNotIn(CAST + "Deem Inferior", game.legal_actions(a))
        game.draw(a, 2)
        game._perform(a, CAST + "Deem Inferior")  # {3}{U} less 2
        run_stack(game)
        self.assertEqual((b.battlefield, b.library[-1]), ([], BEAR))

    def test_deem_inferior_can_put_it_second_from_the_top(self):
        game, _ = table3(None, pick("Second from the top"))
        a, b, _ = game.seats
        a.battlefield, a.hand = lands(4, ISLAND), [DEEM]
        b.battlefield, b.library = [Permanent(BEAR)], [OGRE, OGRE, OGRE]
        game._perform(a, CAST + "Deem Inferior")
        run_stack(game)
        self.assertEqual([c.name for c in b.library], ["Ogre", "Bear", "Ogre", "Ogre"])

    def test_sleep_of_the_dead_skips_only_the_next_untap_step(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, a.hand = lands(1, ISLAND), [SLEEP]
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game._perform(a, CAST + "Sleep of the Dead")
        run_stack(game)
        game.step = "untap"
        game._turn_based_actions(a)  # not its controller's untap step
        game._turn_based_actions(b)
        self.assertTrue(bear.tapped)
        game._turn_based_actions(b)
        self.assertFalse(bear.tapped)

    def test_benevolent_blessing_keeps_its_controllers_auras_but_not_an_opponents(self):
        game, _ = table3(pick("Red"))
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        mine, theirs = Permanent(RED_AURA, attached_to=bear), Permanent(RED_AURA, attached_to=bear)
        a.battlefield, b.battlefield = [bear, mine], [theirs]
        game._enter(a, Permanent(BLESSING, attached_to=bear))
        game._check_state()
        self.assertTrue(game.protected_from(bear, frozenset("R")))
        self.assertEqual((mine.attached_to, theirs in b.battlefield), (bear, False))

    def test_extract_a_confession_takes_the_greatest_power_only_with_evidence(self):
        for answers, lost in (([EVIDENCE_NONE], "Bear"), (["Big", "Big"], "Big")):
            game, _ = table3(script(*answers), script("Bear"))
            a, b, _ = game.seats
            a.battlefield, a.hand, a.graveyard = lands(2), [CONFESSION], [BIG, replace(BIG)]  # 10: enough evidence (two cards)
            b.battlefield = [Permanent(BEAR), Permanent(BIG)]
            game._perform(a, CAST + "Extract a Confession")
            run_stack(game)
            self.assertEqual([c.name for c in b.graveyard], [lost])

    def test_reckoners_bargain_gains_the_sacrificed_mana_value_and_fling_deals_the_sacrificed_power(self):
        game, _ = table3(pick("Big", "Player: B", "Ogre"))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.library = [*lands(4), Permanent(BIG), Permanent(OGRE)], [BARGAIN, FLING], [ISLAND] * 3
        life = a.life
        game._perform(a, CAST + "Reckoner's Bargain")
        run_stack(game)
        self.assertEqual((a.life, len(a.hand)), (life + 5, 3))
        life = b.life
        game._perform(a, CAST + "Fling")
        run_stack(game)
        self.assertEqual(b.life, life - 3)  # the Ogre's power

    def test_melded_moxite_makes_a_tapped_robot(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = lands(3) + [Permanent(MOXITE)]
        activate(game, a, "Melded Moxite")
        robot = next(p for p in a.battlefield if p.card.name == "Robot")
        self.assertTrue(robot.tapped)


if __name__ == "__main__":
    unittest.main()
