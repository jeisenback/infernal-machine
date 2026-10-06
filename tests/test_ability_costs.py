import unittest

from infernal_machine.bot import _limited_cost
from infernal_machine.cards import Card
from infernal_machine.effects import activated_abilities
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature
from tests.test_effects import lands, pick, table

ALTAR = Card(name="Altar", mana_cost="{1}", type_line="Artifact", oracle_text="Sacrifice a creature: Draw a card.")
OTHER = creature("Cultist", 2, 2, "Sacrifice another creature: You gain 2 life.")
SELFISH = creature("Fodder", 1, 1, "Sacrifice a creature: You gain 2 life.")
LOOTER = Card(name="Looter", mana_cost="{1}", type_line="Artifact", oracle_text="{1}, Discard a card: Draw a card.")
GRAVE = Card(name="Grave", mana_cost="{1}", type_line="Artifact",
             oracle_text="{1}, Exile a card from your graveyard: You gain 1 life.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))
SPARE = Card(name="Spare", mana_cost="{1}", type_line="Sorcery", oracle_text="Draw a card.")


def activations(game, seat, text):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and text in a]


def settle(game):
    game._priority_round(game.seats[0])


class ParseTests(unittest.TestCase):
    def test_sacrifice(self):
        (ability,) = activated_abilities(ALTAR)
        self.assertEqual((ability.sacrifice_other, ability.sacrifice_another, ability.sacrifice), ("creature", False, False))
        (other,) = activated_abilities(OTHER)
        self.assertTrue(other.sacrifice_another)

    def test_discard_and_exile(self):
        (looter,) = activated_abilities(LOOTER)
        self.assertEqual((looter.discard, looter.mana_cost), (True, "{1}"))
        (grave,) = activated_abilities(GRAVE)
        self.assertTrue(grave.exile_graveyard)

    def test_the_report_counts_them_as_playable(self):
        for card in (ALTAR, OTHER, LOOTER, GRAVE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_other_amounts_are_still_unsupported(self):
        for text in ("Sacrifice two creatures: Draw a card.", "Discard two cards: Draw a card.",
                     "Exile two cards from your graveyard: Draw a card."):
            self.assertEqual(activated_abilities(Card(name="x", oracle_text=text)), (), text)


class SacrificeTests(unittest.TestCase):
    def test_sacrificing_a_creature_pays_the_cost(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(ALTAR), Permanent(BEAR)]
        settle(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Altar"])
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])
        self.assertEqual(len(a.hand), 1)

    def test_it_needs_a_creature(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(ALTAR)]
        self.assertEqual(activations(game, a, "Altar"), [])

    def test_a_creature_can_sacrifice_itself(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(SELFISH)]
        settle(game)
        self.assertEqual((a.battlefield, a.life), ([], 42))

    def test_another_creature_means_not_itself(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(OTHER)]
        self.assertEqual(activations(game, a, "Cultist"), [])
        a.battlefield.append(Permanent(BEAR))
        self.assertEqual(len(activations(game, a, "Cultist")), 1)

    def test_it_sacrifices_the_other_one(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(OTHER), Permanent(BEAR)]
        settle(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Cultist"])
        self.assertEqual(a.life, 42)

    def test_the_opponents_creatures_cant_be_sacrificed(self):
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(ALTAR)]
        b.battlefield = [Permanent(BEAR)]
        self.assertEqual(activations(game, a, "Altar"), [])


class DiscardAndExileTests(unittest.TestCase):
    def test_discarding_pays_the_cost(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(LOOTER)] + lands(1, MOUNTAIN)
        a.hand = [SPARE]
        settle(game)
        self.assertEqual([c.name for c in a.graveyard], ["Spare"])
        self.assertEqual(len(a.hand), 1)  # drew one

    def test_it_needs_a_card_in_hand(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(LOOTER)] + lands(1, MOUNTAIN)
        self.assertEqual(activations(game, a, "Looter"), [])

    def test_exiling_from_the_graveyard(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(GRAVE)] + lands(1, MOUNTAIN)
        a.graveyard = [SPARE]
        settle(game)
        self.assertEqual((a.graveyard, [c.name for c in a.exile], a.life), ([], ["Spare"], 41))
        self.assertEqual(a.graveyard_left_turn, game.turn)

    def test_it_needs_a_card_in_the_graveyard(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(GRAVE)] + lands(1, MOUNTAIN)
        self.assertEqual(activations(game, a, "Grave"), [])

    def test_it_is_not_offered_without_the_mana_either(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(LOOTER)]
        a.hand = [SPARE]
        self.assertEqual(activations(game, a, "Looter"), [])


class BotTests(unittest.TestCase):
    def test_the_bot_does_not_pay_with_its_own_cards(self):
        for text in ("Sacrifice a creature: Draw a card.", "{1}, Discard a card: Draw a card.",
                     "{1}, Exile a card from your graveyard: You gain 1 life."):
            self.assertFalse(_limited_cost(f"{ACTIVATE}Thing (seat 0, #1): {text}"), text)
        self.assertTrue(_limited_cost(f"{ACTIVATE}Thing (seat 0, #1): {{T}}, Sacrifice this artifact: Draw a card."))


if __name__ == "__main__":
    unittest.main()
