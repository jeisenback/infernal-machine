"""Copy a spell (#659): Jin-Gitaxias, Progress Tyrant ("an artifact, instant, or sorcery spell", copied or countered once each turn),
Kitsa, Otterball Elite ("Activate only if Kitsa's power is 3 or greater"), Storm of Saruman ("copy it, except the copy isn't
legendary"), Wild Ricochet (new targets for a spell, then a copy of it), Bonus Round (each caster copies their own spells this turn)
Sword of Wealth and Power (the next instant or sorcery spell this turn), Krark, the Thumbless (a coin flip with both results),
Zada, Hedron Grinder (a copy for each other creature) and Expansion // Explosion (a spell with mana value 4 or less)."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, BOLT, OGRE, lands, pick, real, run_stack, table

JIN = real("Jin-Gitaxias, Progress Tyrant", "{5}{U}{U}", "Legendary Creature — Phyrexian Praetor",
           "Whenever you cast an artifact, instant, or sorcery spell, copy that spell. You may choose new targets for the copy. This ability "
           "triggers only once each turn. (A copy of a permanent spell becomes a token.)\nWhenever an opponent casts an artifact, instant, or "
           "sorcery spell, counter that spell. This ability triggers only once each turn.", "5", "5", colors=("U",))
KITSA = real("Kitsa, Otterball Elite", "{1}{U}", "Legendary Creature — Otter Wizard",
             "Vigilance\nProwess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)\n{T}: Draw a card, then "
             "discard a card.\n{2}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy. Activate "
             "only if Kitsa's power is 3 or greater.", "1", "3", colors=("U",))
SARUMAN = real("Storm of Saruman", "{4}{U}{U}", "Enchantment",
               "Ward {3}\nWhenever you cast your second spell each turn, copy it, except the copy isn't legendary. You may choose new targets "
               "for the copy. (A copy of a permanent spell becomes a token.)", colors=("U",))
RICOCHET = real("Wild Ricochet", "{2}{R}{R}", "Instant",
                "You may choose new targets for target instant or sorcery spell. Then copy that spell. You may choose new targets for the copy.",
                colors=("R",))
BONUS = real("Bonus Round", "{1}{R}{R}", "Sorcery",
             "Until end of turn, whenever a player casts an instant or sorcery spell, that player copies it and may choose new targets for "
             "the copy.", colors=("R",))
SWORD = real("Sword of Wealth and Power", "{3}", "Artifact — Equipment",
             "Equipped creature gets +2/+2 and has protection from instants and from sorceries.\nWhenever equipped creature deals combat "
             "damage to a player, create a Treasure token. When you next cast an instant or sorcery spell this turn, copy that spell. You may "
             "choose new targets for the copy.\nEquip {2}")
KRARK = real("Krark, the Thumbless", "{1}{R}", "Legendary Creature — Goblin Wizard",
             "Whenever you cast an instant or sorcery spell, flip a coin. If you lose the flip, return that spell to its owner's hand. If you "
             "win the flip, copy that spell, and you may choose new targets for the copy.\nPartner (You can have two commanders if both have "
             "partner.)", "2", "2", colors=("R",))
ZADA = real("Zada, Hedron Grinder", "{3}{R}", "Legendary Creature — Goblin Ally",
            "Whenever you cast an instant or sorcery spell that targets only Zada, copy that spell for each other creature you control that "
            "the spell could target. Each copy targets a different one of those creatures.", "3", "3", colors=("R",))
EXPANSION = real("Expansion", "{U/R}{U/R}", "Instant",
                 "Copy target instant or sorcery spell with mana value 4 or less. You may choose new targets for the copy.", colors=("U", "R"))
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.", colors=("G",))
BIG_STUDY = real("Deep Study", "{5}", "Sorcery", "Draw a card.")
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
TRINKET = real("Trinket", "{1}", "Artifact", "")
CROWN = real("Crown of Ages", "{1}", "Legendary Artifact", "")
STUDY = real("Quick Study", "{1}", "Sorcery", "Draw a card.")


def cast(game, seat, card):
    seat.hand.append(card)
    game._perform(seat, f"Cast: {card.name}")
    run_stack(game)


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class JinGitaxiasTests(unittest.TestCase):
    def board(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(JIN, sick=False)] + lands(6)
        mine.library = [BEAR] * 10
        return game, mine, theirs

    def test_an_artifact_spell_is_copied_as_a_token(self):
        game, mine, theirs = self.board()
        cast(game, mine, TRINKET)
        trinkets = [p for p in mine.battlefield if p.card.name == "Trinket"]
        self.assertEqual(len(trinkets), 2)
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in trinkets), 1)

    def test_only_the_first_spell_each_turn_is_copied(self):
        game, mine, theirs = self.board()
        cast(game, mine, STUDY)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 3)  # 2 + 1: the first one was copied

    def test_a_creature_spell_is_not_copied(self):
        game, mine, theirs = self.board()
        cast(game, mine, BEAR)
        self.assertEqual(names(mine).count("Bear"), 1)

    def test_an_opponents_first_spell_each_turn_is_countered(self):
        game, mine, theirs = self.board()
        game.active = 1
        theirs.battlefield, theirs.library = lands(2), [BEAR] * 5
        cast(game, theirs, BOLT)
        self.assertEqual(theirs.hand, [])  # countered: no card drawn
        cast(game, theirs, BOLT)
        self.assertEqual(len(theirs.hand), 1)


class KitsaTests(unittest.TestCase):
    def offered(self, power_counters):
        game, _, _ = table(pick("Spell:"))
        mine = game.seats[0]
        kitsa = Permanent(KITSA, sick=False)
        kitsa.counters["+1/+1"] = power_counters
        mine.battlefield, mine.library = [kitsa] + lands(4), [BEAR] * 10
        mine.hand = [STUDY]
        game._perform(mine, "Cast: Quick Study")  # (it stays on the stack: Prowess makes Kitsa 1 bigger)
        game._put_triggers_on_stack()
        while len(game.stack) > 1:
            game._resolve(game.stack.pop())
        return game, mine, [a for a in game.legal_actions(mine) if "Copy target" in a]

    def test_at_power_3_the_spell_can_be_copied(self):
        game, mine, actions = self.offered(1)  # 1 + 1 counter + 1 from Prowess
        self.assertEqual(len(actions), 1)
        game._perform(mine, actions[0])
        run_stack(game)
        self.assertEqual(len(mine.hand), 2)

    def test_below_power_3_it_cannot(self):
        self.assertEqual(self.offered(0)[2], [])


class StormOfSarumanTests(unittest.TestCase):
    def board(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(SARUMAN)] + lands(4), [BEAR] * 10
        return game, mine

    def test_the_second_spell_is_copied_and_a_legendary_copy_is_not_legendary(self):
        game, mine = self.board()
        cast(game, mine, TRINKET)
        cast(game, mine, CROWN)
        crowns = [p for p in mine.battlefield if p.card.name == "Crown of Ages"]
        self.assertEqual(len(crowns), 2)  # (two legendary permanents of one name would leave one)
        copy = next(p for p in crowns if p.card.type_line.startswith("Token"))
        self.assertNotIn("Legendary", copy.card.type_line)

    def test_the_first_spell_is_not_copied(self):
        game, mine = self.board()
        cast(game, mine, CROWN)
        self.assertEqual(names(mine).count("Crown of Ages"), 1)


class WildRicochetTests(unittest.TestCase):
    def test_the_spell_is_turned_and_copied(self):
        game, _, _ = table(pick("Spell: Shock", "Player: B"), pick("Player: A"))
        mine, theirs = game.seats
        mine.battlefield, mine.hand = lands(4), [RICOCHET]
        theirs.battlefield, theirs.hand = lands(1), [SHOCK]
        game.active = 1
        game._perform(theirs, "Cast: Shock")  # at A
        game._perform(mine, "Cast: Wild Ricochet")
        run_stack(game)
        self.assertEqual((mine.life, theirs.life), (40, 36))  # the Shock and its copy both at B

    def test_with_no_spell_to_target_it_cannot_be_cast(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.hand = lands(4), [RICOCHET]
        self.assertNotIn("Cast: Wild Ricochet", game.legal_actions(mine))


class BonusRoundTests(unittest.TestCase):
    def test_each_player_copies_their_own_spells_this_turn(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield, mine.library = lands(5), [BEAR] * 10
        theirs.battlefield, theirs.library = lands(2), [BEAR] * 10
        cast(game, mine, BONUS)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 2)
        cast(game, theirs, BOLT)  # (an instant, on A's turn)
        self.assertEqual(len(theirs.hand), 2)  # B's copy, for B

    def test_it_ends_with_the_turn(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = lands(5), [BEAR] * 10
        cast(game, mine, BONUS)
        game.step = "cleanup"
        game._turn_based_actions(mine)
        game.turn += 2
        game.step = "main1"
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 1)


class SwordOfWealthAndPowerTests(unittest.TestCase):
    def hit(self):
        game, _, _ = table()
        mine, theirs = game.seats
        bear, sword = Permanent(BEAR, sick=False), Permanent(SWORD)
        sword.attached_to = bear
        mine.battlefield, mine.library = [bear, sword] + lands(3), [BEAR] * 10
        game.damage(theirs, 4, source=bear, combat=True)
        run_stack(game)
        return game, mine

    def test_a_treasure_and_the_next_instant_or_sorcery_is_copied(self):
        game, mine = self.hit()
        self.assertIn("Treasure", names(mine))
        cast(game, mine, BEAR)  # a creature spell: not the one it waits for
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 2)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 3)  # only the next one


class KrarkTests(unittest.TestCase):
    def flip(self, won):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(KRARK)] + lands(2), [BEAR] * 10
        game.flip_coin = lambda seat: won
        cast(game, mine, STUDY)
        return mine

    def test_a_won_flip_copies_the_spell(self):
        mine = self.flip(True)
        self.assertEqual(len(mine.hand), 2)
        self.assertEqual([c.name for c in mine.graveyard], ["Quick Study"])

    def test_a_lost_flip_returns_it_to_the_hand(self):
        mine = self.flip(False)
        self.assertEqual([c.name for c in mine.hand], ["Quick Study"])
        self.assertEqual(mine.graveyard, [])


class ZadaTests(unittest.TestCase):
    def board(self, target):
        game, _, _ = table(pick(target))
        mine = game.seats[0]
        zada, bear, ogre = Permanent(ZADA, sick=False), Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)
        mine.battlefield = [zada, bear, ogre] + lands(1)
        cast(game, mine, GROWTH)
        return game, zada, bear, ogre

    def test_a_spell_at_zada_is_copied_for_each_other_creature(self):
        game, zada, bear, ogre = self.board("Zada")
        self.assertEqual([game.power(p) for p in (zada, bear, ogre)], [6, 5, 6])

    def test_a_spell_at_another_creature_is_not(self):
        game, zada, bear, ogre = self.board("Bear")
        self.assertEqual([game.power(p) for p in (zada, bear, ogre)], [3, 5, 3])


class ExpansionTests(unittest.TestCase):
    def offered(self, spell):
        game, _, _ = table(pick("Spell:"))
        mine = game.seats[0]
        mine.battlefield, mine.library = lands(8), [BEAR] * 10
        mine.hand = [spell, EXPANSION]
        game._perform(mine, f"Cast: {spell.name}")
        return game, mine, "Cast: Expansion" in game.legal_actions(mine)

    def test_a_spell_of_mana_value_4_or_less_is_copied(self):
        game, mine, castable = self.offered(STUDY)
        self.assertTrue(castable)
        game._perform(mine, "Cast: Expansion")
        run_stack(game)
        self.assertEqual(len(mine.hand), 2)

    def test_a_bigger_spell_is_not_a_target(self):
        self.assertFalse(self.offered(BIG_STUDY)[2])


if __name__ == "__main__":
    unittest.main()
