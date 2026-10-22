"""Morph, Megamorph and Disguise: cast face down for {3} as a 2/2, turn it face up for its own cost."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import MorphCost, morph_of
from infernal_machine.game import CAST, CAST_FACE_DOWN, FACE_DOWN, TURN_UP, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, script, table3

HARUSPEX = real("Grim Haruspex", "{2}{B}", "Creature — Human Wizard", "Morph {B}\nWhenever another nontoken creature you control dies, draw a card.", "3", "2")
DEN = real("Den Protector", "{1}{G}", "Creature — Human Warrior", "Creatures with power less than Den Protector's power can't block it.\n"
           "Megamorph {1}{G}\nWhen Den Protector is turned face up, return target card from your graveyard to your hand.", "2", "1")
DISGUISER = real("Disguised Dog", "{2}{B}", "Creature — Dog", "Menace\nWhen this creature enters, you gain 2 life.\nDisguise {1}{B}", "3", "3")
FLIER = real("Flying Morph", "{4}{U}", "Creature — Bird", "Flying\nMorph {U}\nWhen this creature is turned face up, draw a card.", "3", "3")
HYDRA = real("Hooded Hydra", "{X}{G}{G}", "Creature — Snake Hydra", "Morph {3}{G}{G}\nAs this creature is turned face up, put five +1/+1 counters on it.", "0", "0")
PLAIN = real("Plain Creature", "{2}", "Creature — Bear", "", "2", "2")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def table(card, n=3, graveyard=()):
    game, _ = table3(script("Pass"))
    a = game.seats[0]
    a.hand, a.battlefield, a.library, a.graveyard = [card], lands(n), [FOREST] * 5, list(graveyard)
    return game, a


def cast_face_down(card, n=3):
    game, a = table(card, n)
    game._perform(a, CAST_FACE_DOWN + card.name)
    return game, a


def settled(card, n=3):
    game, a = cast_face_down(card, n)
    run_stack(game)
    game._check_state()
    [face_down] = [p for p in a.battlefield if p.manifested]
    return game, a, face_down


class ParseTests(unittest.TestCase):
    def test_the_morph_line_is_understood_and_read(self):
        for card in (HARUSPEX, DEN, DISGUISER, FLIER):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual([morph_of(c) for c in (HARUSPEX, DEN, DISGUISER, PLAIN)],
                         [("Morph", MorphCost("{B}")), ("Megamorph", MorphCost("{1}{G}")), ("Disguise", MorphCost("{1}{B}")), None])


class CastingFaceDownTests(unittest.TestCase):
    def test_it_is_offered_for_three_mana_at_sorcery_speed_and_only_for_a_morph_card(self):
        game, a = table(HARUSPEX)
        self.assertIn(CAST_FACE_DOWN + "Grim Haruspex", game.legal_actions(a))
        game, a = table(PLAIN)
        self.assertNotIn(CAST_FACE_DOWN + "Plain Creature", game.legal_actions(a))
        game, a = table(HARUSPEX, n=2)
        self.assertNotIn(CAST_FACE_DOWN + "Grim Haruspex", game.legal_actions(a))
        game, a = table(HARUSPEX)
        game.step, game.active = "end", 1
        self.assertNotIn(CAST_FACE_DOWN + "Grim Haruspex", game.legal_actions(a))

    def test_it_costs_three_whatever_the_card_costs(self):
        game, a = cast_face_down(HARUSPEX, n=5)
        self.assertEqual(sum(p.tapped for p in a.battlefield), 3)

    def test_the_spell_on_the_stack_is_a_colorless_nameless_2_2_creature(self):
        game, a = cast_face_down(HARUSPEX)
        item = game.stack[-1]
        self.assertEqual((item.card, item.physical), (FACE_DOWN, HARUSPEX))
        self.assertEqual((item.card.power, item.card.toughness, item.card.colors, item.card.cmc), ("2", "2", (), 3.0))
        self.assertEqual(a.hand, [])

    def test_a_countered_face_down_spell_is_the_real_card_in_the_graveyard(self):
        game, a = cast_face_down(HARUSPEX)
        game.counter(game.stack[-1])
        self.assertEqual([c.name for c in a.graveyard], ["Grim Haruspex"])

    def test_it_enters_as_a_2_2_with_no_abilities(self):
        game, a, down = settled(FLIER)
        self.assertEqual((down.card, down.real_card), (FACE_DOWN, FLIER))
        self.assertEqual((game.power(down), game.toughness(down), game.has_keyword(down, "flying")), (2, 2, False))

    def test_it_can_die_and_goes_to_the_graveyard_as_the_real_card(self):
        game, a, down = settled(HARUSPEX)
        game.destroy(down)
        self.assertEqual([c.name for c in a.graveyard], ["Grim Haruspex"])
        self.assertEqual([p for p in a.battlefield if p.manifested], [])


class TurningFaceUpTests(unittest.TestCase):
    def test_it_is_turned_up_for_the_morph_cost_not_the_mana_cost(self):
        game, a, down = settled(HARUSPEX, n=4)
        for land in a.battlefield:
            land.tapped = False
        label = TURN_UP + game.label(down)
        self.assertIn(label, game.legal_actions(a))
        game._perform(a, label)
        self.assertEqual(sum(p.tapped for p in a.battlefield), 1)  # {B}, not {2}{B}
        self.assertEqual((down.card, down.real_card, down.manifested), (HARUSPEX, None, False))
        self.assertEqual((game.power(down), game.toughness(down)), (3, 2))

    def test_it_cannot_be_turned_up_without_the_mana(self):
        game, a, down = settled(HARUSPEX)  # all three lands tapped for the cast
        self.assertNotIn(TURN_UP + game.label(down), game.legal_actions(a))

    def test_it_can_be_turned_up_at_instant_speed(self):
        game, a, down = settled(HARUSPEX, n=4)
        for land in a.battlefield:
            land.tapped = False
        game.step, game.active = "end", 1
        self.assertIn(TURN_UP + game.label(down), game.legal_actions(a))

    def test_the_turned_face_up_trigger(self):
        game, a, down = settled(FLIER, n=4)
        for land in a.battlefield:
            land.tapped = False
        hand = len(a.hand)
        game._perform(a, TURN_UP + game.label(down))
        run_stack(game)
        self.assertEqual(len(a.hand), hand + 1)
        self.assertTrue(game.has_keyword(down, "flying"))

    def test_turning_up_does_not_enter_the_battlefield_again(self):
        game, a, down = settled(DISGUISER, n=4)
        for land in a.battlefield:
            land.tapped = False
        game._perform(a, TURN_UP + game.label(down))
        run_stack(game)
        self.assertEqual(a.life, 40)  # "When this creature enters, you gain 2 life" never happened

    def test_megamorph_adds_a_counter(self):
        game, a, down = settled(DEN, n=5)
        for land in a.battlefield:
            land.tapped = False
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual(down.counters.get("+1/+1"), 1)

    def test_as_this_creature_is_turned_face_up_counters(self):
        game, a, down = settled(HYDRA, n=8)
        for land in a.battlefield:
            land.tapped = False
        game._perform(a, TURN_UP + game.label(down))
        run_stack(game)
        self.assertEqual((down.counters.get("+1/+1"), game.power(down)), (5, 5))

    def test_an_ordinary_morph_gets_no_counter(self):
        game, a, down = settled(HARUSPEX, n=4)
        for land in a.battlefield:
            land.tapped = False
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual(down.counters, {})

    def test_disguise_has_ward_two_while_face_down(self):
        game, a, down = settled(DISGUISER)
        self.assertEqual(game.ward_of(down), "{2}")
        game, a, down = settled(HARUSPEX)
        self.assertFalse(game.ward_of(down))


def with_morph(line, name="Odd Morph"):
    return real(name, "{3}{B}", "Creature — Zombie", f"{line}\nWhen this creature is turned face up, you gain 1 life.", "3", "3")


class OtherCostTests(unittest.TestCase):
    """Morph costs that are not mana: the face-down creature stays when only three lands paid for it."""

    def turned_up_game(self, line, *, hand=(), mine=(), life=40, answers=("Pass",)):
        card = with_morph(line)
        game, _ = table3(script(*answers))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [card, *hand], lands(3), [FOREST] * 5
        a.life = life
        game._perform(a, CAST_FACE_DOWN + card.name)
        run_stack(game)
        a.battlefield += [Permanent(c) for c in mine]
        [down] = [p for p in a.battlefield if p.manifested]
        return game, a, down

    def offered(self, game, a, down):
        return TURN_UP + game.label(down) in game.legal_actions(a)

    def test_the_costs_are_read(self):
        read = {line: morph_of(with_morph(line))[1] for line in (
            "Morph\u2014Sacrifice another creature.", "Morph\u2014Reveal a black card in your hand.", "Morph\u2014Discard a card.",
            "Morph\u2014Discard a Zombie card.", "Morph\u2014Pay 5 life.", "Morph\u2014Return two Islands you control to their owner's hand.",
            "Morph\u2014Return a Bird you control to its owner's hand.", "Morph\u2014Sacrifice two Mountains.")}
        self.assertEqual(list(read.values()), [
            MorphCost(sacrifice="another creature"), MorphCost(reveal="B"), MorphCost(discard="card"), MorphCost(discard="Zombie"),
            MorphCost(life=5), MorphCost(bounce="Island", count=2), MorphCost(bounce="Bird"), MorphCost(sacrifice="Mountain", count=2)])
        self.assertEqual(unsupported_lines(with_morph("Morph\u2014Sacrifice another creature.")), [])
        self.assertEqual(unsupported_lines(with_morph("Morph\u2014Juggle three goblins.")), ["Morph\u2014Juggle three goblins."])

    def test_reveal_a_card_of_a_color(self):
        black = real("Black Card", "{B}", "Sorcery", "", colors=("B",))
        game, a, down = self.turned_up_game("Morph\u2014Reveal a black card in your hand.", hand=[black])
        self.assertTrue(self.offered(game, a, down))
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual(([c.name for c in a.hand], down.manifested), (["Black Card"], False))  # revealed, not spent
        game, a, down = self.turned_up_game("Morph\u2014Reveal a black card in your hand.", hand=[real("Red Card", "{R}", "Sorcery", "", colors=("R",))])
        self.assertFalse(self.offered(game, a, down))

    def test_discard_a_card(self):
        game, a, down = self.turned_up_game("Morph\u2014Discard a card.", hand=[PLAIN])
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), ([], ["Plain Creature"]))
        game, a, down = self.turned_up_game("Morph\u2014Discard a card.")
        self.assertFalse(self.offered(game, a, down))  # nothing to discard

    def test_discard_a_zombie_card(self):
        zombie = real("Zombie Card", "{B}", "Creature — Zombie", "", "1", "1")
        game, a, down = self.turned_up_game("Morph\u2014Discard a Zombie card.", hand=[PLAIN])
        self.assertFalse(self.offered(game, a, down))
        game, a, down = self.turned_up_game("Morph\u2014Discard a Zombie card.", hand=[PLAIN, zombie])
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual([c.name for c in a.graveyard], ["Zombie Card"])

    def test_pay_life(self):
        game, a, down = self.turned_up_game("Morph\u2014Pay 5 life.")
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual(a.life, 35)
        game, a, down = self.turned_up_game("Morph\u2014Pay 5 life.", life=4)
        self.assertFalse(self.offered(game, a, down))
        game, a, down = self.turned_up_game("Morph\u2014Pay 5 life.", life=5)
        self.assertTrue(self.offered(game, a, down))

    def test_sacrifice_another_creature(self):
        game, a, down = self.turned_up_game("Morph\u2014Sacrifice another creature.")
        self.assertFalse(self.offered(game, a, down))  # it cannot sacrifice itself
        game, a, down = self.turned_up_game("Morph\u2014Sacrifice another creature.", mine=[BEAR])
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Odd Morph"])
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])

    def test_sacrifice_two_lands_of_a_type(self):
        mountain = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
        game, a, down = self.turned_up_game("Morph\u2014Sacrifice two Mountains.", mine=[mountain])
        self.assertFalse(self.offered(game, a, down))
        game, a, down = self.turned_up_game("Morph\u2014Sacrifice two Mountains.", mine=[mountain, mountain])
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual([c.name for c in a.graveyard], ["Mountain", "Mountain"])

    def test_return_permanents_you_control_to_your_hand(self):
        island = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
        game, a, down = self.turned_up_game("Morph\u2014Return two Islands you control to their owner's hand.", mine=[island])
        self.assertFalse(self.offered(game, a, down))
        game, a, down = self.turned_up_game("Morph\u2014Return two Islands you control to their owner's hand.", mine=[island, island])
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual([c.name for c in a.hand], ["Island", "Island"])
        bird = real("Raven", "{U}", "Creature — Bird", "", "1", "1")
        game, a, down = self.turned_up_game("Morph\u2014Return a Bird you control to its owner's hand.", mine=[BEAR])
        self.assertFalse(self.offered(game, a, down))  # a Bear is not a Bird
        game, a, down = self.turned_up_game("Morph\u2014Return a Bird you control to its owner's hand.", mine=[bird])
        game._perform(a, TURN_UP + game.label(down))
        self.assertEqual([c.name for c in a.hand], ["Raven"])

    def test_no_mana_is_spent_and_the_trigger_still_happens(self):
        game, a, down = self.turned_up_game("Morph\u2014Pay 5 life.")
        game._perform(a, TURN_UP + game.label(down))
        run_stack(game)
        self.assertEqual((a.life, down.card.name), (36, "Odd Morph"))  # paid 5, gained 1


if __name__ == "__main__":
    unittest.main()
