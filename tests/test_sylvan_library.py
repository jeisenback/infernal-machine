"""Sylvan Library, from its Oracle text: two more cards in the draw step, then each of two drawn cards costs 4 life or goes back."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import SYLVAN_CHOOSE_PROMPT, SYLVAN_PAY_PROMPT, SYLVAN_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real

LIBRARY = real("Sylvan Library", "{1}{G}", "Enchantment",
               "At the beginning of your draw step, you may draw two additional cards. If you do, choose two cards in your hand drawn this turn. "
               "For each of those cards, pay 4 life or put the card on top of your library.")


def card(name):
    return Card(name=name, type_line="Sorcery", oracle_text="Draw a card.")


def answers(**by_prompt):
    """A policy answering each kind of question from a list, by the start of the options it picks (the first of the list is next)."""
    queues = {key: list(values) for key, values in by_prompt.items()}

    def policy(prompt, options):
        for key, queue in queues.items():
            if prompt.startswith(globals()[key]) and queue:
                wanted = queue.pop(0)
                return next((i for i, option in enumerate(options) if option.startswith(wanted)), 0)
        return 0
    return policy


def draw_step(*policy_args, library=("A", "B", "C", "D", "E"), life=40, **by_prompt):
    game, _ = table3(answers(**by_prompt))
    a = game.seats[0]
    a.battlefield = [Permanent(LIBRARY)]
    a.library = [card(n) for n in library]
    a.hand = []
    a.life = life
    game.draw(a, 1)  # the draw step's own card
    game.trigger("draw_step", a.battlefield[0], a)
    run_stack(game)
    return game, a


class SylvanTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(LIBRARY), [])

    def test_declining_draws_nothing_more(self):
        game, a = draw_step(SYLVAN_PROMPT=["No"])
        self.assertEqual(([c.name for c in a.hand], a.life), (["A"], 40))

    def test_paying_life_for_both_keeps_all_three_cards(self):
        game, a = draw_step(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["B", "C"], SYLVAN_PAY_PROMPT=["Pay", "Pay"])
        self.assertEqual(([c.name for c in a.hand], a.life), (["A", "B", "C"], 32))

    def test_putting_both_back_leaves_the_top_in_reverse_order(self):
        game, a = draw_step(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["B", "C"], SYLVAN_PAY_PROMPT=["Put", "Put"])
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.library[:2]], a.life), (["A"], ["C", "B"], 40))

    def test_one_of_each(self):
        game, a = draw_step(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["B", "C"], SYLVAN_PAY_PROMPT=["Pay", "Put"])
        self.assertEqual(([c.name for c in a.hand], a.library[0].name, a.life), (["A", "B"], "C", 36))

    def test_the_card_from_the_draw_step_can_be_chosen(self):
        game, a = draw_step(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["A", "B"], SYLVAN_PAY_PROMPT=["Put", "Put"])
        self.assertEqual([c.name for c in a.hand], ["C"])

    def test_only_cards_drawn_this_turn_can_be_chosen(self):
        game, _ = table3(answers(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["Old", "A"], SYLVAN_PAY_PROMPT=["Pay", "Pay"]))
        a = game.seats[0]
        a.battlefield = [Permanent(LIBRARY)]
        a.library = [card(n) for n in "ABCD"]
        a.hand = [card("Old")]  # kept from an earlier turn
        game.draw(a, 1)
        game.trigger("draw_step", a.battlefield[0], a)
        run_stack(game)
        # "Old" was never an option, so the first answer fell back to the first card drawn
        self.assertEqual(sorted(c.name for c in a.hand), ["A", "B", "C", "Old"])
        self.assertEqual(a.life, 32)

    def test_a_card_drawn_on_an_earlier_turn_is_not_eligible_even_if_it_was_drawn(self):
        game, _ = table3(answers(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["A", "B"], SYLVAN_PAY_PROMPT=["Put", "Put"]))
        a = game.seats[0]
        a.battlefield = [Permanent(LIBRARY)]
        a.library = [card(n) for n in "ABCDE"]
        game.draw(a, 1)  # "A", drawn last turn and kept
        game.turn += 1
        game.draw(a, 1)  # "B", this turn's draw step card
        game.trigger("draw_step", a.battlefield[0], a)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.hand), ["A", "D"])  # "A" was not a choice: B and C (this turn's) went back, D stayed

    def test_with_four_life_or_less_the_card_has_to_go_back(self):
        game, a = draw_step(SYLVAN_PROMPT=["Yes"], SYLVAN_CHOOSE_PROMPT=["B", "C"], SYLVAN_PAY_PROMPT=["Pay", "Pay"], life=4)
        self.assertEqual(([c.name for c in a.hand], a.life), (["A"], 4))


if __name__ == "__main__":
    unittest.main()
