"""The copy lines of issue #80 (Rionya first). Lines are the cards' own Oracle text from Scryfall; each has cases where the
effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import activate, BEAR, card, lands, OGRE, pick, run_stack, table3

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


MUDDLE = Card(name="Muddle, the Ever-Changing", mana_cost="{1}{U}{R}", type_line="Legendary Creature — Elemental Otter Shapeshifter",
              power="1", toughness="1",
              oracle_text="Whenever you cast an instant or sorcery spell, Muddle, the Ever-Changing becomes a copy of up to one "
                          "target nonlegendary creature you control until end of turn, except it has myriad. (Whenever it "
                          "attacks, for each opponent other than defending player, you may create a token copy that's tapped "
                          "and attacking that player or a planeswalker they control. Exile the tokens at end of combat.)")
KING = Card(name="King", mana_cost="{2}{W}", cmc=3.0, type_line="Legendary Creature — Human", power="3", toughness="3")
MYRIAD_BEAR = Card(name="Myriad Bear", type_line="Creature — Bear", power="2", toughness="2", oracle_text="Myriad")


class MuddleTests(unittest.TestCase):
    def cast(self, spell, target="Bear", caster=0):
        game, _ = table3(pick(target))
        a, b, c = game.seats
        self.muddle, self.bear = Permanent(MUDDLE), Permanent(BEAR_CARD)
        self.king, self.theirs = Permanent(KING), Permanent(BEAR_CARD)
        a.battlefield, b.battlefield = [self.muddle, self.bear, self.king], [self.theirs]
        game.seats[caster].cast_log.append((game.turn, spell))
        game._observe("cast", spell, game.seats[caster])
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(MUDDLE), [])

    def test_it_becomes_a_copy_with_myriad_until_end_of_turn(self):
        game, a = self.cast(BOLT)
        self.assertEqual((self.muddle.card.name, game.power(self.muddle)), ("Bear", 2))
        self.assertTrue(game.has_keyword(self.muddle, "myriad"))
        self.assertEqual(self.muddle.original.name, "Muddle, the Ever-Changing")  # restored at cleanup

    def test_a_creature_spell_does_not_trigger_it(self):
        game, a = self.cast(BEAR_CARD)
        self.assertEqual(self.muddle.card.name, "Muddle, the Ever-Changing")

    def test_an_opponents_spell_does_not_trigger_it(self):
        game, a = self.cast(BOLT, caster=1)
        self.assertEqual(self.muddle.card.name, "Muddle, the Ever-Changing")

    def test_it_may_copy_nothing(self):
        game, a = self.cast(BOLT, target="No target")
        self.assertEqual(self.muddle.card.name, "Muddle, the Ever-Changing")

    def test_legendary_creatures_and_opponents_creatures_are_not_offered(self):
        offered = []
        game, _ = table3(lambda prompt, options: offered.append(list(options)) or len(options) - 1)
        a, b, _ = game.seats
        muddle = Permanent(MUDDLE)
        a.battlefield, b.battlefield = [muddle, Permanent(KING)], [Permanent(BEAR_CARD)]
        a.cast_log.append((game.turn, BOLT))
        game._observe("cast", BOLT, a)
        run_stack(game)
        self.assertEqual(muddle.card.name, "Muddle, the Ever-Changing")
        self.assertTrue(all("King" not in "".join(o) and "Bear" not in "".join(o) for o in offered))


class MyriadTests(unittest.TestCase):
    def attack(self, answer="Yes", opponents=2):
        picks = iter([1])
        yes = lambda prompt, options: (next(picks, 0) if prompt.startswith("Attack") and len(options) > 1
                                       else options.index("Yes") if answer == "Yes" and "Yes" in options else
                                       options.index("No") if "No" in options else 0)
        game, _ = table3(yes)
        a, b, c = game.seats
        self.creature = Permanent(MYRIAD_BEAR, sick=False)
        a.battlefield = [self.creature]
        game.combat.declare_attackers(a)
        run_stack(game)
        return game, a, b, c

    def tokens(self, game, a):
        return [at for at in game.combat.attacks if at.attacker is not self.creature]

    def test_the_keyword_is_supported(self):
        self.assertEqual(unsupported_lines(MYRIAD_BEAR), [])

    def test_a_copy_attacks_each_other_opponent(self):
        game, a, b, c = self.attack()
        [token] = self.tokens(game, a)
        self.assertEqual((token.attacker.card.name, token.attacker.tapped), ("Myriad Bear", True))
        self.assertIs(token.defender, c)  # the creature attacks b; the copy attacks c

    def test_the_copies_are_exiled_at_end_of_combat(self):
        game, a, b, c = self.attack()
        game.step = "main2"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Myriad Bear"])

    def test_it_is_optional(self):
        game, a, b, c = self.attack(answer="No")
        self.assertEqual(self.tokens(game, a), [])


MIRROR = Card(name="Cursed Mirror", mana_cost="{3}", cmc=3.0, type_line="Artifact",
              oracle_text="{T}: Add {R}.\nAs this artifact enters, you may have it become a copy of any creature on the battlefield "
                          "until end of turn, except it has haste.")


class CursedMirrorTests(unittest.TestCase):
    def enter(self, choice):
        game, _ = table3(pick(choice))
        a, b, _ = game.seats
        b.battlefield = [Permanent(KING)]
        a.battlefield = [Permanent(BEAR_CARD)]
        mirror = Permanent(MIRROR, sick=True)
        game._enter(a, mirror)
        return game, a, mirror

    def test_parse(self):
        self.assertEqual(unsupported_lines(MIRROR), [])

    def test_it_enters_as_a_copy_with_haste(self):
        game, a, mirror = self.enter("Bear")
        self.assertEqual((mirror.card.name, game.power(mirror), "Creature" in mirror.card.type_line), ("Bear", 2, True))
        self.assertTrue(game.has_keyword(mirror, "haste"))

    def test_any_creature_may_be_copied_even_an_opponents_legend(self):
        game, a, mirror = self.enter("King")
        self.assertEqual(mirror.card.name, "King")

    def test_it_turns_back_into_the_artifact_at_cleanup(self):
        game, a, mirror = self.enter("Bear")
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual((mirror.card.name, mirror.card.type_line), ("Cursed Mirror", "Artifact"))

    def test_it_may_stay_an_artifact(self):
        game, a, mirror = self.enter("Don't copy")
        self.assertEqual(mirror.card.name, "Cursed Mirror")

    def test_with_no_creature_on_the_battlefield_it_is_just_an_artifact(self):
        game, _ = table3(pick("Idol", "Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(Card(name="Idol", type_line="Artifact"))]  # only a creature may be copied
        mirror = Permanent(MIRROR, sick=True)
        game._enter(a, mirror)
        self.assertEqual(mirror.card.name, "Cursed Mirror")


from infernal_machine.game import CAST  # noqa: E402

DRAKE = Card(name="Thunderclap Drake", mana_cost="{3}{U}", type_line="Creature — Drake", power="3", toughness="2",
             oracle_text="Flying\nInstant and sorcery spells you cast cost {1} less to cast.\n{2}{U}, Sacrifice this creature: When you "
                         "next cast an instant or sorcery spell this turn, copy it for each time you've cast your commander from "
                         "the command zone this game. You may choose new targets for the copies.")
STUDY = Card(name="Study", mana_cost="{U}", cmc=1.0, type_line="Instant", oracle_text="Draw a card.")


class ThunderclapDrakeTests(unittest.TestCase):
    def play(self, casts, spell=STUDY):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(DRAKE)] + lands(6)
        a.commander_casts = casts
        a.library = [BEAR_CARD] * 20
        activate(game, a, "Sacrifice")
        a.hand = [spell]
        game._perform(a, CAST + spell.name)
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(DRAKE), [])

    def test_a_copy_for_each_time_the_commander_was_cast(self):
        game, a = self.play({"Commander": 2})
        self.assertEqual(len(a.hand), 3)  # the spell and its two copies each drew a card

    def test_the_commander_casts_of_every_commander_add_up(self):
        game, a = self.play({"One": 1, "Two": 1})
        self.assertEqual(len(a.hand), 3)

    def test_no_commander_casts_means_no_copies(self):
        game, a = self.play({})
        self.assertEqual(len(a.hand), 1)
        self.assertIsNone(a.copy_next_turn)

    def test_only_the_next_instant_or_sorcery_is_copied(self):
        game, a = self.play({"Commander": 1})
        a.hand.append(Card(name="Study2", mana_cost="{U}", cmc=1.0, type_line="Instant", oracle_text="Draw a card."))
        game._perform(a, CAST + "Study2")
        run_stack(game)
        self.assertEqual(len(a.hand), 3)  # 2 from the first spell and its copy, 1 from the second

    def test_a_creature_spell_is_not_copied_and_the_wait_continues(self):
        game, a = self.play({"Commander": 1}, spell=Card(name="Cheap", mana_cost="{U}", cmc=1.0, type_line="Creature — Bear", power="1", toughness="1"))
        self.assertEqual(a.copy_next_turn, game.turn)


HOFRI = Card(name="Hofri Ghostforge", mana_cost="{2}{R}{W}", type_line="Legendary Creature — Dwarf Cleric", power="3", toughness="4",
             oracle_text="Spirits you control get +1/+1 and have trample and haste.\nWhenever another nontoken creature you control "
                         "dies, exile it. If you do, create a token that's a copy of that creature, except it's a Spirit in "
                         "addition to its other types and it has \"When this token leaves the battlefield, return the exiled card "
                         "to its owner's graveyard.\"")
CLERIC = Card(name="Cleric", mana_cost="{1}{W}", cmc=2.0, type_line="Creature — Human Cleric", power="2", toughness="2",
              oracle_text="Vigilance")


class HofriGhostforgeTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.hofri = Permanent(HOFRI)
        a.battlefield = [self.hofri]
        return game, a, b

    def die(self, game, seat, permanent):
        seat.battlefield.append(permanent)
        game._leave_battlefield(permanent, "destroyed")
        run_stack(game)

    def spirits(self, seat):
        return [p for p in seat.battlefield if p is not self.hofri and "Spirit" in p.card.type_line]

    def test_parse(self):
        self.assertEqual(unsupported_lines(HOFRI), [])

    def test_the_dead_creature_is_exiled_and_comes_back_as_a_spirit_token(self):
        game, a, b = self.table()
        self.die(game, a, Permanent(CLERIC))
        [spirit] = self.spirits(a)
        self.assertEqual((spirit.card.name, spirit.card.type_line), ("Cleric", "Token Creature — Human Cleric Spirit"))
        self.assertEqual(([c.name for c in a.exile], a.graveyard), (["Cleric"], []))
        self.assertTrue(game.has_keyword(spirit, "vigilance"))  # a copy of the creature

    def test_hofris_own_spirits_get_the_bonus(self):
        game, a, b = self.table()
        self.die(game, a, Permanent(CLERIC))
        [spirit] = self.spirits(a)
        self.assertEqual((game.power(spirit), game.has_keyword(spirit, "haste")), (3, True))

    def test_when_the_token_leaves_the_card_goes_to_the_graveyard(self):
        game, a, b = self.table()
        self.die(game, a, Permanent(CLERIC))
        [spirit] = self.spirits(a)
        game._leave_battlefield(spirit, "destroyed")
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Cleric"], []))

    def test_a_token_is_not_copied(self):
        game, a, b = self.table()
        self.die(game, a, Permanent(Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1")))
        self.assertEqual(self.spirits(a), [])

    def test_an_opponents_creature_is_not_copied(self):
        game, a, b = self.table()
        self.die(game, b, Permanent(CLERIC))
        self.assertEqual((self.spirits(a), self.spirits(b)), ([], []))

    def test_hofri_itself_is_not_copied(self):
        game, a, b = self.table()
        game._leave_battlefield(self.hofri, "destroyed")
        run_stack(game)
        self.assertEqual([p for p in a.battlefield], [])

    def test_a_card_that_left_the_graveyard_in_response_is_not_copied(self):
        game, a, b = self.table()
        a.battlefield.append(dead := Permanent(CLERIC))
        game._leave_battlefield(dead, "destroyed")
        a.graveyard.clear()  # exiled or returned before the trigger resolves
        run_stack(game)
        self.assertEqual(self.spirits(a), [])


DRAGON = Card(name="Mirrorwing Dragon", mana_cost="{3}{R}{R}", type_line="Creature — Dragon", power="4", toughness="5",
              oracle_text="Flying\nWhenever a player casts an instant or sorcery spell that targets only this creature, that player "
                          "copies that spell for each other creature they control that the spell could target. Each copy targets a "
                          "different one of those creatures.")
GROWTH = Card(name="Growth", mana_cost="{G}", cmc=1.0, type_line="Instant", colors=("G",),
              oracle_text="Target creature gets +3/+3 until end of turn.")
WARDED_BEAR = Card(name="Warded Bear", type_line="Creature — Bear", power="2", toughness="2", oracle_text="Protection from green")


class MirrorwingDragonTests(unittest.TestCase):
    def cast(self, target, caster=0, others=("Bear", "Ogre"), spell=GROWTH):
        game, _ = table3(pick(target), pick(target))
        a, b, _ = game.seats
        self.dragon = Permanent(DRAGON)
        mine = {"Bear": BEAR_CARD, "Ogre": Card(name="Ogre", type_line="Creature — Ogre", power="3", toughness="3"),
                "Warded": WARDED_BEAR}
        self.others = [Permanent(mine[n]) for n in others]
        a.battlefield = [self.dragon] + (self.others if caster == 0 else [])
        b.battlefield = self.others if caster == 1 else []
        seat = game.seats[caster]
        seat.hand, seat.battlefield = [spell], seat.battlefield + lands(2)
        from infernal_machine.game import CAST as _CAST
        game._perform(seat, _CAST + spell.name)
        run_stack(game)
        return game

    def test_parse(self):
        self.assertEqual(unsupported_lines(DRAGON), [])

    def test_every_other_creature_you_control_gets_a_copy(self):
        game = self.cast("Mirrorwing Dragon")
        self.assertEqual([game.power(self.dragon)] + [game.power(p) for p in self.others], [7, 5, 6])

    def test_the_caster_is_the_one_who_copies(self):
        game = self.cast("Mirrorwing Dragon", caster=1)  # the opponent aims it at the dragon; their own creatures get the copies
        self.assertEqual([game.power(self.dragon)] + [game.power(p) for p in self.others], [7, 5, 6])

    def test_a_creature_the_spell_could_not_target_gets_no_copy(self):
        game = self.cast("Mirrorwing Dragon", others=("Warded", "Ogre"))
        self.assertEqual([game.power(p) for p in self.others], [2, 6])

    def test_a_spell_aimed_at_another_creature_is_not_copied(self):
        game = self.cast("Bear")
        self.assertEqual([game.power(self.dragon)] + [game.power(p) for p in self.others], [4, 5, 3])

    def test_a_spell_that_is_not_an_instant_or_sorcery_does_not_trigger_it(self):
        aura_like = Card(name="Growth Wish", mana_cost="{G}", cmc=1.0, type_line="Enchantment", colors=("G",), oracle_text="Target creature gets +3/+3 until end of turn.")
        game = self.cast("Mirrorwing Dragon", spell=aura_like)
        self.assertEqual([game.power(p) for p in self.others], [2, 3])
