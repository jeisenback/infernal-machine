import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Combat
from infernal_machine.effects import LivingWeapon, echo_cost, triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, table3

LAND = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))


def creature(name, text, power=2, toughness=2, types="Creature — Bear"):
    return Card(name=name, mana_cost="{1}", type_line=types, oracle_text=text, power=str(power), toughness=str(toughness))


def spell(name, cost, cmc, text, type_line="Instant"):
    return Card(name=name, mana_cost=cost, cmc=float(cmc), type_line=type_line, oracle_text=text)


def resolve_everything(game):
    game._put_triggers_on_stack()
    while game.stack:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()
    game._check_state()


def cast(game, seat, card):
    seat.cast_log.append((game.turn, card))
    game._observe("cast", card, seat)
    resolve_everything(game)


class ProwessTests(unittest.TestCase):
    MONK = creature("Monk", "Prowess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)")

    def test_a_noncreature_spell_pumps_it(self):
        game, _ = table3()
        a = game.seats[0]
        monk = Permanent(self.MONK)
        a.battlefield = [monk]
        cast(game, a, spell("Bolt", "{R}", 1, "Draw a card."))
        self.assertEqual((game.power(monk), game.toughness(monk)), (3, 3))
        cast(game, a, spell("Bolt", "{R}", 1, "Draw a card."))
        self.assertEqual(game.power(monk), 4)  # each spell adds one

    def test_creature_spells_and_opponents_spells_do_not(self):
        game, _ = table3()
        a, b, _ = game.seats
        monk = Permanent(self.MONK)
        a.battlefield = [monk]
        cast(game, a, spell("Bear", "{1}{G}", 2, "", "Creature — Bear"))
        cast(game, b, spell("Bolt", "{R}", 1, "Draw a card."))
        self.assertEqual(game.power(monk), 2)

    def test_the_bonus_ends_with_the_turn(self):
        game, _ = table3()
        a = game.seats[0]
        monk = Permanent(self.MONK)
        a.battlefield = [monk]
        cast(game, a, spell("Bolt", "{R}", 1, "Draw a card."))
        monk.until_end_of_turn.clear()
        self.assertEqual(game.power(monk), 2)

    def test_the_report_accepts_the_keywords(self):
        for text in ("Prowess", "Flying, prowess", "Devoid", "Shadow", "Skulk", "Delve", "Cascade", "Living weapon"):
            self.assertEqual(unsupported_lines(creature("Test", text)), [], text)


class LivingWeaponTests(unittest.TestCase):
    BLADE = Card(name="Blade", mana_cost="{3}", type_line="Artifact — Equipment",
                 oracle_text="Living weapon (When this Equipment enters, create a 0/0 black Phyrexian Germ creature token, "
                             "then attach this to it.)\nEquipped creature gets +1/+1.\nEquip {2}")

    def test_it_makes_a_germ_and_attaches(self):
        game, _ = table3()
        a = game.seats[0]
        blade = Permanent(self.BLADE)
        game._enter(a, blade)
        resolve_everything(game)
        germ = next(p for p in a.battlefield if p is not blade)
        self.assertEqual((germ.card.name, germ.card.colors), ("Phyrexian Germ", ("B",)))
        self.assertIs(blade.attached_to, germ)
        self.assertEqual((game.power(germ), game.toughness(germ)), (1, 1))  # 0/0 plus the Equipment

    def test_the_germ_dies_without_the_equipment(self):
        game, _ = table3()
        a = game.seats[0]
        blade = Permanent(self.BLADE)
        game._enter(a, blade)
        resolve_everything(game)
        game._leave_battlefield(blade, "destroyed")
        game._check_state()
        self.assertEqual(a.battlefield, [])

    def test_parse(self):
        [ability] = triggered_abilities(self.BLADE)
        self.assertEqual((ability.event, ability.effects), ("enters", (LivingWeapon(),)))


class EvasionTests(unittest.TestCase):
    def can_block(self, attacker_text, blocker_text, attacker_power=2, blocker_power=2):
        game, _ = table3()
        a, b, _ = game.seats
        attacker = Permanent(creature("Attacker", attacker_text, attacker_power))
        blocker = Permanent(creature("Blocker", blocker_text, blocker_power))
        a.battlefield, b.battlefield = [attacker], [blocker]
        game.combat = Combat(game)
        return game.combat._can_block(blocker, attacker)

    def test_shadow_is_blocked_only_by_shadow(self):
        self.assertFalse(self.can_block("Shadow", ""))
        self.assertTrue(self.can_block("Shadow", "Shadow"))

    def test_shadow_creatures_can_block_only_shadow(self):
        self.assertFalse(self.can_block("", "Shadow"))

    def test_skulk_cannot_be_blocked_by_greater_power(self):
        self.assertFalse(self.can_block("Skulk", "", attacker_power=2, blocker_power=3))
        self.assertTrue(self.can_block("Skulk", "", attacker_power=2, blocker_power=2))
        self.assertTrue(self.can_block("Skulk", "", attacker_power=2, blocker_power=1))
        self.assertTrue(self.can_block("", "", attacker_power=2, blocker_power=9))


class EchoTests(unittest.TestCase):
    GUIDE = creature("Guide", "Echo {1} (At the beginning of your upkeep, if this came under your control since the "
                              "beginning of your last upkeep, sacrifice it unless you pay its echo cost.)")

    def upkeep(self, game, seat):
        for p in seat.battlefield:
            p.tapped = False
        game.step = "upkeep"
        game._turn_based_actions(seat)

    def test_pay_once(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        guide = Permanent(self.GUIDE)
        a.battlefield = [*lands(2)]
        game._enter(a, guide)
        self.assertTrue(guide.echo_pending)
        self.upkeep(game, a)
        self.assertEqual((guide in a.battlefield, guide.echo_pending, sum(p.tapped for p in a.battlefield)), (True, False, 1))
        self.upkeep(game, a)  # nothing more is due
        self.assertEqual(sum(p.tapped for p in a.battlefield), 0)
        self.assertIn(guide, a.battlefield)

    def test_decline_or_cannot_pay_and_it_is_sacrificed(self):
        for policy, board in ((pick("No"), lands(2)), (pick("Yes"), [])):
            game, _ = table3(policy)
            a = game.seats[0]
            guide = Permanent(self.GUIDE)
            a.battlefield = list(board)
            game._enter(a, guide)
            self.upkeep(game, a)
            self.assertNotIn(guide, a.battlefield)
            self.assertEqual([c.name for c in a.graveyard], ["Guide"])

    def test_only_on_your_upkeep(self):
        game, _ = table3(pick("Yes"))
        a, b, _ = game.seats
        guide = Permanent(self.GUIDE)
        a.battlefield = [*lands(2)]
        game._enter(a, guide)
        self.upkeep(game, b)
        self.assertTrue(guide.echo_pending)
        self.assertEqual(echo_cost(self.GUIDE), "{1}")


class DelveTests(unittest.TestCase):
    CRUISE = spell("Treasure Cruise", "{7}{U}", 8, "Delve (Each card you exile from your graveyard while casting this spell "
                   "pays for {1}.)\nDraw three cards.", "Sorcery")

    def board(self, lands_count, graveyard_cards):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 5
        a.hand = [self.CRUISE]
        a.battlefield = lands(lands_count)
        a.graveyard = [Card(name=f"Card {n}", type_line="Sorcery") for n in range(graveyard_cards)]
        return game, a

    def test_exiles_as_few_cards_as_it_needs(self):
        game, a = self.board(5, 6)  # {7}{U}: five lands, so three cards pay for the rest
        game._perform(a, CAST + "Treasure Cruise")
        self.assertEqual((len(a.graveyard), len(a.exile)), (3, 3))
        resolve_everything(game)
        self.assertEqual(len(a.hand), 3)

    def test_a_graveyard_big_enough_is_castable(self):
        game, a = self.board(2, 6)
        self.assertIn(CAST + "Treasure Cruise", game.legal_actions(a))  # two lands and six cards: eight
        game, a = self.board(2, 5)
        self.assertNotIn(CAST + "Treasure Cruise", game.legal_actions(a))  # seven

    def test_only_generic_mana_can_be_delved(self):
        game, a = self.board(0, 20)
        self.assertNotIn(CAST + "Treasure Cruise", game.legal_actions(a))  # the {U} still needs a source

    def test_no_delve_when_the_lands_are_enough(self):
        game, a = self.board(8, 6)
        game._perform(a, CAST + "Treasure Cruise")
        self.assertEqual(len(a.graveyard), 6)


class CascadeTests(unittest.TestCase):
    ENGINE = spell("Cascade Engine", "{2}{R}{R}", 4, "Cascade (When you cast this spell, exile cards from the top of your "
                   "library until you exile a nonland card that costs less. You may cast it without paying its mana "
                   "cost. Put the exiled cards on the bottom of your library in a random order.)\nDraw a card.", "Sorcery")
    FREE = spell("Free Spell", "{1}{R}", 2, "You gain 3 life.", "Sorcery")
    BIG = spell("Big Spell", "{4}{R}", 5, "You gain 9 life.", "Sorcery")

    def cast(self, library, choose="Yes"):
        game, _ = table3(pick(choose))
        a = game.seats[0]
        a.library = list(library)
        a.hand = [self.ENGINE]
        a.battlefield = lands(4)
        game._perform(a, CAST + "Cascade Engine")
        resolve_everything(game)
        return game, a

    def test_casts_the_first_cheaper_nonland_card_for_free(self):
        game, a = self.cast([LAND, self.BIG, self.FREE, BEAR, BEAR])
        self.assertEqual(a.life, 43)  # Free Spell resolved
        self.assertIn(self.FREE, a.graveyard)
        self.assertEqual(len(a.hand), 1)  # and Cascade Engine's own draw
        bottom = [c.name for c in a.library[-2:]]
        self.assertEqual(sorted(bottom), ["Big Spell", "Wastes"])  # the cards it passed over go to the bottom
        self.assertEqual(a.exile, [])

    def test_the_cascade_spell_goes_on_the_stack_above_the_original(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.library = [self.FREE]
        a.hand = [self.ENGINE]
        a.battlefield = lands(4)
        game._perform(a, CAST + "Cascade Engine")
        self.assertEqual([item.ability is not None for item in game.stack], [False, True])

    def test_declining_puts_it_on_the_bottom_too(self):
        game, a = self.cast([self.FREE, BEAR], choose="No")
        self.assertEqual(a.life, 40)
        self.assertEqual([c.name for c in a.library], ["Free Spell"])  # the Bear was drawn by Cascade Engine itself
        self.assertEqual(a.exile, [])

    def test_nothing_to_find(self):
        game, a = self.cast([LAND, LAND, self.BIG])
        self.assertEqual(a.life, 40)
        everything = sorted(c.name for c in a.hand + a.library)
        self.assertEqual(everything, ["Big Spell", "Wastes", "Wastes"])  # all three went to the bottom, one then drawn
        self.assertEqual(a.exile, [])

    def test_it_must_cost_less_than_the_cascade_spell(self):
        equal = spell("Same Cost", "{2}{R}{R}", 4, "You gain 1 life.", "Sorcery")
        game, a = self.cast([equal, self.FREE])
        self.assertEqual(a.life, 43)  # Same Cost was passed over, Free Spell was cast


if __name__ == "__main__":
    unittest.main()
