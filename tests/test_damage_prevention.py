"""Damage prevention, first slice (#235), from the cards' real Oracle text (CR 615): "Prevent all damage that would be dealt to you this
turn." and its kin for this turn (`Game.prevention_rules`), Maze of Ith and Restrain's combat damage to and by one creature, and the statics
of Fog Bank, Muzzle, Ghostly Possession, Dolmen Gate, The Wanderer, Tajic and Frenzied Baloth's "Combat damage can't be prevented."."""

import unittest

from infernal_machine.combat import Attack
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, lands, pick, real, run_stack, table3

MAZE = real("Maze of Ith", "", "Land", "{T}: Untap target attacking creature. Prevent all combat damage that would be dealt to and dealt by "
            "that creature this turn.")
RIOT = real("Riot Control", "{2}{W}", "Instant", "You gain 1 life for each creature your opponents control. Prevent all damage that would be "
            "dealt to you this turn.", colors=("W",))
HAZE = real("Obscuring Haze", "{2}{G}", "Instant", "If you control a commander, you may cast this spell without paying its mana cost.\nPrevent "
            "all damage that would be dealt this turn by creatures your opponents control.", colors=("G",))
GATE = real("Dolmen Gate", "{2}", "Artifact", "Prevent all combat damage that would be dealt to attacking creatures you control.")
LIGHT = real("Divine Light", "{W}", "Sorcery", "Prevent all damage that would be dealt this turn to creatures you control.", colors=("W",))
FESTIVITIES = real("Commencement of Festivities", "{1}{G}", "Instant", "Prevent all combat damage that would be dealt to players this turn.",
                   colors=("G",))
RESTRAIN = real("Restrain", "{2}{W}", "Instant", "Prevent all combat damage that would be dealt by target attacking creature this turn.\nDraw "
                "a card.", colors=("W",))
FOG_BANK = real("Fog Bank", "{1}{U}", "Creature — Wall", "Defender (This creature can't attack.)\nFlying\nPrevent all combat damage that "
                "would be dealt to and dealt by this creature.", "0", "2", colors=("U",))
BALOTH = real("Frenzied Baloth", "{G}{G}", "Creature — Beast", "This spell can't be countered.\nTrample, haste\nCreature spells you control "
              "can't be countered.\nCombat damage can't be prevented.", "3", "2", colors=("G",))
MUZZLE = real("Muzzle", "{1}{W}", "Enchantment — Aura", "Enchant creature\nPrevent all damage that would be dealt by enchanted creature.",
              colors=("W",))
POSSESSION = real("Ghostly Possession", "{2}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature has flying.\nPrevent all combat "
                  "damage that would be dealt to and dealt by enchanted creature.", colors=("W",))
WANDERER = real("The Wanderer", "{3}{W}", "Legendary Planeswalker", "Prevent all noncombat damage that would be dealt to you and other "
                "permanents you control.\n−2: Exile target creature with power 4 or greater.", colors=("W",))
TAJIC = real("Tajic, Legion's Edge", "{1}{R}{W}", "Legendary Creature — Human Soldier", "Haste\nMentor (Whenever this creature attacks, put a "
             "+1/+1 counter on target attacking creature with lesser power.)\nPrevent all noncombat damage that would be dealt to other "
             "creatures you control.\n{R}{W}: Tajic gains first strike until end of turn.", "3", "2", colors=("R", "W"))
RESPITE = real("Blessed Respite", "{1}{G}", "Instant", "Target player shuffles their graveyard into their library. Prevent all combat damage "
               "that would be dealt this turn.", colors=("G",))
CARDS = (MAZE, RIOT, HAZE, GATE, LIGHT, FESTIVITIES, RESTRAIN, FOG_BANK, BALOTH, MUZZLE, POSSESSION, WANDERER, TAJIC, RESPITE)


def cast(game, seat, card):
    seat.battlefield += lands(6)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


class DamagePreventionTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_riot_control_prevents_damage_to_you_only_this_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        theirs = Permanent(OGRE)
        b.battlefield = [theirs]
        cast(game, a, RIOT)
        mine = Permanent(BEAR)
        a.battlefield.append(mine)
        game.damage(a, 3, source=theirs)
        game.damage(mine, 1, source=theirs)
        game.damage(b, 2, source=mine)
        self.assertEqual((a.life, mine.damage, b.life), (41, 1, 38))  # it gained 1 for the Ogre; its creature and the others aren't covered
        game.turn += 1
        game.damage(a, 3, source=theirs)
        self.assertEqual(a.life, 38)

    def test_obscuring_haze_stops_only_the_opponents_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        theirs, mine = Permanent(OGRE), Permanent(BEAR)
        b.battlefield, a.battlefield = [theirs], [mine]
        cast(game, a, HAZE)
        game.damage(a, 3, source=theirs)
        game.damage(b, 2, source=mine)
        self.assertEqual((a.life, b.life), (40, 38))

    def test_divine_light_covers_your_creatures_not_you(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine, theirs = Permanent(BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield = [mine], [theirs]
        cast(game, a, LIGHT)
        game.damage(mine, 2, source=Permanent(OGRE))
        game.damage(theirs, 1, source=Permanent(OGRE))
        game.damage(a, 2, source=Permanent(OGRE))
        self.assertEqual((mine.damage, theirs.damage, a.life), (0, 1, 38))

    def test_commencement_prevents_combat_damage_to_players_only(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        cast(game, a, FESTIVITIES)
        game.damage(b, 2, source=Permanent(OGRE), combat=True)
        game.damage(b, 2, source=Permanent(OGRE))
        game.damage(bear, 1, source=Permanent(OGRE), combat=True)
        self.assertEqual((b.life, bear.damage), (38, 1))

    def test_maze_of_ith_untaps_and_shuts_off_one_attacker(self):
        game, _ = table3(pick("Gray"))
        a, b, _ = game.seats
        attacker, other = Permanent(OGRE), Permanent(BEAR)
        attacker.tapped = True
        b.battlefield = [attacker, other]
        a.battlefield = [Permanent(MAZE), Permanent(FOG_BANK)]
        game.combat.attacks = [Attack(attacker, b, a), Attack(other, b, a)]
        activate(game, a, "Untap target attacking creature")
        self.assertFalse(attacker.tapped)
        game.damage(a, 3, source=attacker, combat=True)
        game.damage(attacker, 2, source=Permanent(BEAR), combat=True)
        game.damage(a, 2, source=other, combat=True)
        self.assertEqual((a.life, attacker.damage), (38, 0))

    def test_restrain_stops_what_the_creature_deals_not_what_it_takes(self):
        game, _ = table3(pick("Gray"))
        a, b, _ = game.seats
        attacker = Permanent(OGRE)
        b.battlefield, a.library = [attacker], [FOREST]
        game.combat.attacks = [Attack(attacker, b, a)]
        cast(game, a, RESTRAIN)
        game.damage(a, 3, source=attacker, combat=True)
        game.damage(attacker, 2, source=Permanent(BEAR), combat=True)
        self.assertEqual((a.life, attacker.damage, len(a.hand)), (40, 2, 1))

    def test_fog_bank_neither_takes_nor_deals_combat_damage(self):
        game, _ = table3()
        a, b, _ = game.seats
        bank, ogre = Permanent(FOG_BANK), Permanent(OGRE)
        a.battlefield, b.battlefield = [bank], [ogre]
        game.damage(bank, 3, source=ogre, combat=True)
        game.damage(ogre, 1, source=bank, combat=True)
        game.damage(bank, 1, source=ogre)  # noncombat damage still counts
        self.assertEqual((bank.damage, ogre.damage), (1, 0))

    def test_frenzied_baloth_lets_combat_damage_through_a_fog_bank(self):
        game, _ = table3()
        a, b, _ = game.seats
        bank, ogre = Permanent(FOG_BANK), Permanent(OGRE)
        a.battlefield, b.battlefield = [bank], [ogre, Permanent(BALOTH)]
        game.damage(bank, 1, source=ogre, combat=True)
        self.assertEqual(bank.damage, 1)

    def test_muzzle_and_ghostly_possession_follow_the_creature_they_enchant(self):
        game, _ = table3()
        a, b, _ = game.seats
        muzzled, possessed, other = Permanent(OGRE), Permanent(BEAR), Permanent(BEAR)
        b.battlefield = [muzzled, possessed, other, Permanent(MUZZLE, attached_to=muzzled), Permanent(POSSESSION, attached_to=possessed)]
        game.damage(a, 3, source=muzzled)  # any damage it would deal
        game.damage(a, 2, source=possessed, combat=True)  # combat damage it would deal ...
        game.damage(possessed, 1, source=other, combat=True)  # ... or be dealt
        game.damage(possessed, 1, source=other)  # (not noncombat damage)
        game.damage(a, 2, source=other, combat=True)
        self.assertEqual((a.life, possessed.damage), (38, 1))

    def test_dolmen_gate_protects_your_attackers_only(self):
        game, _ = table3()
        a, b, _ = game.seats
        attacking, home, theirs = Permanent(OGRE), Permanent(BEAR), Permanent(OGRE)
        a.battlefield, b.battlefield = [Permanent(GATE), attacking, home], [theirs]
        game.combat.attacks = [Attack(attacking, a, b), Attack(theirs, b, a)]
        for creature in (attacking, home, theirs):
            game.damage(creature, 1, source=Permanent(BEAR), combat=True)
        self.assertEqual((attacking.damage, home.damage, theirs.damage), (0, 1, 1))

    def test_the_wanderer_and_tajic_prevent_noncombat_damage(self):
        game, _ = table3()
        a, b, _ = game.seats
        wanderer, tajic, bear = Permanent(WANDERER, loyalty=5), Permanent(TAJIC), Permanent(BEAR)
        a.battlefield = [wanderer, bear]
        game.damage(a, 2, source=Permanent(OGRE))
        game.damage(bear, 1, source=Permanent(OGRE))
        game.damage(a, 2, source=Permanent(OGRE), combat=True)
        self.assertEqual((a.life, bear.damage), (38, 0))
        b.battlefield = [tajic, Permanent(OGRE)]
        game.damage(b.battlefield[1], 1, source=Permanent(BEAR))
        game.damage(tajic, 1, source=Permanent(BEAR))  # not Tajic itself: "other creatures"
        self.assertEqual((b.battlefield[1].damage, tajic.damage), (0, 1))

    def test_blessed_respite_shuffles_a_graveyard_and_fogs(self):
        game, _ = table3(pick("Player: B"))
        a, b, _ = game.seats
        b.graveyard = [BEAR, OGRE]
        library = len(b.library)
        cast(game, a, RESPITE)
        game.damage(a, 3, source=Permanent(OGRE), combat=True)
        self.assertEqual((b.graveyard, len(b.library), a.life), ([], library + 2, 40))


if __name__ == "__main__":
    unittest.main()
