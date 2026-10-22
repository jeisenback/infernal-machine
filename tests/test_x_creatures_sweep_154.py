"""The seven X creatures of the precon decks that no test named (issue #154), each cast with X chosen from its real Oracle text,
with X of 0, an odd X where the rounding matters, and cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import attack_all, battlefield_names, BEAR, BIG, BIRD, FOREST, lands, OGRE, pick, real, RELIC, run_stack, table, Table, table3

FOOD = Card(name="Food", type_line="Token Artifact — Food")


def counters(permanent):
    return permanent.counters.get("+1/+1", 0)


def the(table, name):
    return next((p for p in table.a.battlefield if p.card.name == name), None)


def fight(game, seat):
    """One combat: `seat`'s creatures that are not summoning sick attack the first opponent and the defender blocks."""
    game.active = seat.index
    game.combat.declare_attackers(seat)
    run_stack(game)
    game.combat.declare_blockers()
    run_stack(game)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)


PRODIGY = real("Ingenious Prodigy", "{X}{U}", "Creature — Human Wizard",
               "Skulk (This creature can't be blocked by creatures with greater power.)\nThis creature enters with X +1/+1 counters on it.\nAt "
               "the beginning of your upkeep, if this creature has one or more +1/+1 counters on it, you may remove a +1/+1 counter from "
               "it. If you do, draw a card.", "0", "1")


class IngeniousProdigyTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PRODIGY), [])

    def test_it_enters_with_x_counters(self):
        t = Table(PRODIGY, "3").cast()
        prodigy = the(t, "Ingenious Prodigy")
        self.assertEqual((counters(prodigy), t.game.power(prodigy), t.game.toughness(prodigy)), (3, 3, 4))

    def test_x_of_zero_is_a_zero_one(self):
        t = Table(PRODIGY, "0").cast()
        self.assertEqual((counters(the(t, "Ingenious Prodigy")), t.game.power(the(t, "Ingenious Prodigy"))), (0, 0))

    def upkeep(self, with_counters, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        prodigy = Permanent(PRODIGY, counters={"+1/+1": with_counters} if with_counters else {})
        a.battlefield = [prodigy]
        a.library = [FOREST] * 5
        game.trigger("upkeep", prodigy, a)
        run_stack(game)
        return prodigy, a

    def test_upkeep_it_may_remove_a_counter_to_draw(self):
        prodigy, a = self.upkeep(2, "Yes")
        self.assertEqual((counters(prodigy), len(a.hand)), (1, 1))

    def test_it_may_decline(self):
        prodigy, a = self.upkeep(2, "No")
        self.assertEqual((counters(prodigy), len(a.hand)), (2, 0))

    def test_without_counters_it_does_nothing(self):
        prodigy, a = self.upkeep(0, "Yes")
        self.assertEqual(len(a.hand), 0)

    def blocked_by(self, blocker_power):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        prodigy = Permanent(PRODIGY, counters={"+1/+1": 1}, sick=False)  # a 1/2
        a.battlefield = [prodigy]
        b.battlefield = [Permanent(real("Blocker", "{1}", "Creature — Test", "", str(blocker_power), "3"), sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        return bool(game.combat.attacks[0].blockers)

    def test_skulk_a_creature_with_greater_power_cannot_block_it(self):
        self.assertFalse(self.blocked_by(2))
        self.assertTrue(self.blocked_by(1))


HYDRA = real("Goldvein Hydra", "{X}{G}", "Creature — Hydra",
             "Vigilance, trample, haste\nThis creature enters with X +1/+1 counters on it.\nWhen this creature dies, create a number of tapped "
             "Treasure tokens equal to its power.", "0", "0")


class GoldveinHydraTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(HYDRA), [])

    def test_it_enters_with_x_counters_and_its_keywords(self):
        t = Table(HYDRA, "3").cast()
        hydra = the(t, "Goldvein Hydra")
        self.assertEqual((counters(hydra), t.game.power(hydra)), (3, 3))
        self.assertTrue(all(t.game.has_keyword(hydra, k) for k in ("vigilance", "trample", "haste")))

    def test_x_of_zero_dies_at_once_and_makes_no_treasure(self):
        t = Table(HYDRA, "0").cast()
        self.assertEqual(sum(p.card.name == "Treasure" for p in t.a.battlefield), 0)
        self.assertIsNone(the(t, "Goldvein Hydra"))

    def test_when_it_dies_it_makes_that_many_tapped_treasures(self):
        t = Table(HYDRA, "3").cast()
        hydra = the(t, "Goldvein Hydra")
        t.game.destroy(hydra)
        run_stack(t.game)
        treasures = [p for p in t.a.battlefield if p.card.name == "Treasure"]
        self.assertEqual((len(treasures), all(p.tapped for p in treasures)), (3, True))

    def test_a_pumped_hydra_counts_its_power_when_it_dies(self):
        t = Table(HYDRA, "2").cast()
        hydra = the(t, "Goldvein Hydra")
        t.game.put_counters(hydra, "+1/+1", 2)
        t.game.destroy(hydra)
        run_stack(t.game)
        self.assertEqual(sum(p.card.name == "Treasure" for p in t.a.battlefield), 4)


GOOSE = real("The Goose Mother", "{X}{G}{U}", "Legendary Creature — Bird Hydra",
             "Flying\nThe Goose Mother enters with X +1/+1 counters on it.\nWhen The Goose Mother enters, create half X Food tokens, rounded up."
             "\nWhenever The Goose Mother attacks, you may sacrifice a Food. If you do, draw a card.", "2", "2")


class TheGooseMotherTests(unittest.TestCase):
    def foods(self, t):
        return sum(p.card.name == "Food" for p in t.a.battlefield)

    def test_parse(self):
        self.assertEqual(unsupported_lines(GOOSE), [])

    def test_it_enters_with_x_counters(self):
        t = Table(GOOSE, "4").cast()
        self.assertEqual(counters(the(t, "The Goose Mother")), 4)

    def test_half_x_food_rounded_up(self):
        for x, expected in ((0, 0), (1, 1), (2, 1), (3, 2), (4, 2)):
            t = Table(GOOSE, str(x), n=8).cast()
            self.assertEqual(self.foods(t), expected, x)

    def attack(self, foods, *choices):
        game, _ = table3(pick("Attack", *choices))
        a = game.seats[0]
        goose = Permanent(GOOSE, sick=False)
        a.battlefield = [goose] + [Permanent(FOOD) for _ in range(foods)]
        a.library = [FOREST] * 5
        fight(game, a)
        return a

    def test_attacking_it_may_sacrifice_a_food_to_draw(self):
        a = self.attack(2, "Yes", "Food")
        self.assertEqual((len(a.hand), sum(p.card.name == "Food" for p in a.battlefield)), (1, 1))

    def test_it_may_decline(self):
        a = self.attack(2, "No")
        self.assertEqual((len(a.hand), sum(p.card.name == "Food" for p in a.battlefield)), (0, 2))

    def test_without_food_it_draws_nothing(self):
        a = self.attack(0, "Yes")
        self.assertEqual(len(a.hand), 0)


KRASIS = real("Hydroid Krasis", "{X}{G}{U}", "Creature — Jellyfish Hydra Beast",
              "When you cast this spell, you gain half X life and draw half X cards. Round down each time.\nFlying, trample\nThis creature "
              "enters with X +1/+1 counters on it.", "0", "0")


class HydroidKrasisTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(KRASIS), [])

    def test_half_x_life_and_cards_rounded_down(self):
        for x, expected in ((0, 0), (1, 0), (2, 1), (5, 2), (6, 3)):
            t = Table(KRASIS, str(x), n=8).cast()
            self.assertEqual((t.a.life - 40, len(t.a.hand)), (expected, expected), x)

    def test_it_enters_with_x_counters_flying_and_trample(self):
        t = Table(KRASIS, "5", n=8).cast()
        krasis = the(t, "Hydroid Krasis")
        self.assertEqual((counters(krasis), t.game.power(krasis)), (5, 5))
        self.assertTrue(t.game.has_keyword(krasis, "flying") and t.game.has_keyword(krasis, "trample"))

    def test_the_cast_trigger_does_not_need_it_to_resolve(self):
        t = Table(KRASIS, "4", n=8)
        t.game._perform(t.a, CAST + "Hydroid Krasis")  # the spell is on the stack; the trigger has gone on top of it
        run_stack(t.game)
        self.assertEqual((t.a.life, len(t.a.hand)), (42, 2))

    def test_x_of_zero_krasis_dies(self):
        t = Table(KRASIS, "0").cast()
        self.assertIsNone(the(t, "Hydroid Krasis"))


SERPENT = real("Stonecoil Serpent", "{X}", "Artifact Creature — Snake", "Reach, trample, protection from multicolored\nThis creature enters "
                                                                         "with X +1/+1 counters on it.", "0", "0")
GOLD = real("Gold", "{1}{G}{U}", "Creature — Test", "", "2", "2", colors=("G", "U"))
GREEN = real("Green", "{1}{G}", "Creature — Test", "", "2", "2", colors=("G",))


class StonecoilSerpentTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SERPENT), [])

    def test_it_costs_x_and_enters_with_x_counters(self):
        t = Table(SERPENT, "4", n=4).cast()
        serpent = the(t, "Stonecoil Serpent")
        self.assertEqual((counters(serpent), t.game.power(serpent)), (4, 4))

    def test_x_of_zero_dies(self):
        t = Table(SERPENT, "0").cast()
        self.assertIsNone(the(t, "Stonecoil Serpent"))

    def blocked_by(self, blocker):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(SERPENT, counters={"+1/+1": 3}, sick=False)]
        b.battlefield = [Permanent(blocker, sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        return bool(game.combat.attacks[0].blockers)

    def test_a_multicolored_creature_cannot_block_it_and_a_monocolored_one_can(self):
        self.assertFalse(self.blocked_by(GOLD))
        self.assertTrue(self.blocked_by(GREEN))

    def test_a_colorless_creature_can_block_it(self):
        self.assertTrue(self.blocked_by(OGRE))


SPIRALMANCER = real("Owlin Spiralmancer", "{3}{U}", "Creature — Bird Wizard",
                    "Flying, vigilance\nWhenever you cast your first spell with {X} in its mana cost each turn, you may copy it. You may "
                    "choose new targets for the copy. (A copy of a permanent spell becomes a token.)", "3", "4")
STROKE = real("Stroke of Genius", "{X}{2}{U}", "Instant", "Target player draws X cards.")
PLAIN_SPELL = real("Plain Draw", "{1}{U}", "Instant", "Target player draws two cards.")


class OwlinSpiralmancerTests(unittest.TestCase):
    def table(self, card, *answers, mine_extra=(), n=8):
        t = Table(card, *answers, n=n, mine=[Permanent(SPIRALMANCER), *mine_extra])
        t.a.library = [FOREST] * 20
        t.b.library = [FOREST] * 20
        return t

    def test_parse(self):
        self.assertEqual(unsupported_lines(SPIRALMANCER), [])

    def test_the_first_x_spell_each_turn_may_be_copied(self):
        t = self.table(STROKE, "2", "Player: A", "Yes", "Player: A").cast()
        self.assertEqual(len(t.a.hand), 4)  # the spell and its copy each draw two

    def test_the_copy_may_have_a_new_target(self):
        t = self.table(STROKE, "2", "Player: A", "Yes", "Player: B").cast()
        self.assertEqual((len(t.a.hand), len(t.b.hand)), (2, 2))

    def test_it_may_decline_the_copy(self):
        t = self.table(STROKE, "2", "Player: A", "No").cast()
        self.assertEqual(len(t.a.hand), 2)

    def test_a_spell_without_x_is_not_copied(self):
        t = self.table(PLAIN_SPELL, "Player: A", "Yes", "Player: A").cast()
        self.assertEqual(len(t.a.hand), 2)

    def test_only_the_first_x_spell_each_turn(self):
        t = self.table(STROKE, "1", "Player: A", "Yes", "Player: A")
        t.a.hand.append(STROKE)
        t.cast()
        self.assertEqual(len(t.a.hand), 2 + 1)  # one X spell and its copy drew one each; the other Stroke is still in hand
        t.game._perform(t.a, CAST + "Stroke of Genius")
        run_stack(t.game)
        self.assertEqual(len(t.a.hand), 0 + 1 + 1)  # the second cast drew one card and was not copied

    def test_an_opponents_x_spell_is_not_copied(self):
        t = self.table(STROKE, n=8)
        t.b.hand, t.b.battlefield = [STROKE], lands(8)
        t.game.active = 1
        t.b.player.policy = pick("1", "Player: B", "Yes")
        t.game._perform(t.b, CAST + "Stroke of Genius")
        run_stack(t.game)
        self.assertEqual(len(t.b.hand), 1)

    def test_a_permanent_x_spell_is_copied_as_a_token(self):
        t = self.table(SERPENT, "2", "Yes", n=8).cast()
        serpents = [p for p in t.a.battlefield if p.card.name == "Stonecoil Serpent"]
        self.assertEqual(sorted(counters(p) for p in serpents), [2, 2])
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in serpents), 1)

    def test_the_token_copy_leaves_no_card_behind_when_it_dies(self):
        t = self.table(SERPENT, "2", "Yes", n=8).cast()
        token = next(p for p in t.a.battlefield if p.card.type_line.startswith("Token"))
        t.game.destroy(token)
        run_stack(t.game)
        self.assertEqual([c.name for c in t.a.graveyard], [])


OTTER = real("Elusive Otter", "{U}", "Creature — Otter",
             "Prowess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)\nCreatures with power less than "
             "this creature's power can't block it.", "1", "1")
CANTRIP = real("Cantrip", "{U}", "Instant", "Draw a card.")


class ElusiveOtterTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(OTTER), [])

    def test_a_noncreature_spell_gives_it_plus_one_plus_one_until_end_of_turn(self):
        otter = Permanent(OTTER)
        t = Table(CANTRIP, mine=[otter]).cast()
        self.assertEqual((t.game.power(otter), t.game.toughness(otter)), (2, 2))

    def test_a_creature_spell_does_not(self):
        otter = Permanent(OTTER)
        t = Table(real("Beast", "{1}", "Creature — Beast", "", "1", "1"), mine=[otter]).cast()
        self.assertEqual(t.game.power(otter), 1)

    def blocked_by(self, blocker, pumped=0):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        otter = Permanent(OTTER, counters={"+1/+1": pumped} if pumped else {}, sick=False)
        a.battlefield = [otter]
        b.battlefield = [Permanent(blocker, sick=False)]
        game.active = 0
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        return bool(game.combat.attacks[0].blockers)

    def test_a_creature_with_less_power_cannot_block_it(self):
        weak = real("Weak", "{1}", "Creature — Test", "", "1", "3")
        self.assertFalse(self.blocked_by(weak, pumped=1))  # the Otter is a 2/2, the blocker has power 1
        self.assertTrue(self.blocked_by(weak))  # equal power can block

    def test_a_creature_with_equal_or_greater_power_can_block_it(self):
        self.assertTrue(self.blocked_by(BEAR, pumped=1))
        self.assertTrue(self.blocked_by(OGRE, pumped=1))
