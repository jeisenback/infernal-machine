"""Graveyard exile, return and cast lines of issue #80: Currency Converter, Quintorius, Excava, Augusta, Renegade Bull and
Sevinne's Reclamation. Lines are the cards' own Oracle text from Scryfall; each has cases where it must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import activate, fire
from tests.test_triggers_80 import FOREST, RELIC, SHRINE, card

CONVERTER = Card(name="Currency Converter", mana_cost="{1}", cmc=1.0, type_line="Artifact",
                 oracle_text="Whenever you discard a card, you may exile that card from your graveyard.\n{2}, {T}: Draw a card, "
                             "then discard a card.\n{T}: Put a card exiled with this artifact into its owner's graveyard. If it's a "
                             "land card, create a Treasure token. If it's a nonland card, create a 2/2 black Rogue creature token.")
GOLEM = Card(name="Golem", mana_cost="{3}", cmc=3.0, type_line="Artifact Creature — Golem", power="3", toughness="3")


class CurrencyConverterTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.converter = Permanent(CONVERTER)
        a.battlefield = [self.converter]
        a.library = [FOREST] * 10
        return game, a

    def discard_and_exile(self, game, a, *cards):
        for c in cards:
            a.hand = [c]
            game.discard(a, 1)
            run_stack(game)

    def tokens(self, a):
        return sorted(p.card.name for p in a.battlefield if p.card.type_line.startswith("Token"))

    def test_parse(self):
        self.assertEqual(unsupported_lines(CONVERTER), [])

    def test_a_nonland_card_becomes_a_rogue(self):
        game, a = self.table("Yes", "Golem")
        self.discard_and_exile(game, a, GOLEM)
        self.assertEqual([c.name for c in a.exile], ["Golem"])
        activate(game, a, "Put a card exiled")
        run_stack(game)
        self.assertEqual((self.tokens(a), [c.name for c in a.graveyard], a.exile), (["Rogue"], ["Golem"], []))
        rogue = next(p for p in a.battlefield if p.card.name == "Rogue")
        self.assertEqual((rogue.card.power, rogue.card.toughness, rogue.card.colors), ("2", "2", ("B",)))

    def test_a_land_card_becomes_a_treasure(self):
        game, a = self.table("Yes", "Forest")
        self.discard_and_exile(game, a, FOREST)
        activate(game, a, "Put a card exiled")
        run_stack(game)
        self.assertEqual((self.tokens(a), [c.name for c in a.graveyard]), (["Treasure"], ["Forest"]))

    def test_you_choose_which_exiled_card(self):
        game, a = self.table("Yes", "Yes", "Forest")
        self.discard_and_exile(game, a, GOLEM, FOREST)
        activate(game, a, "Put a card exiled")
        run_stack(game)
        self.assertEqual((self.tokens(a), [c.name for c in a.exile]), (["Treasure"], ["Golem"]))

    def test_it_cannot_be_activated_with_nothing_exiled_with_it(self):
        game, a = self.table()
        self.assertFalse([x for x in game.legal_actions(a) if "Put a card exiled" in x])

    def test_a_card_exiled_by_something_else_is_not_exiled_with_it(self):
        game, a = self.table()
        a.graveyard = [GOLEM]
        a.exile = []
        game.exile_card_from_graveyard(a, GOLEM, False)  # no source ability is resolving
        self.assertFalse([x for x in game.legal_actions(a) if "Put a card exiled" in x])


QUINTORIUS = Card(name="Quintorius, Loremaster", mana_cost="{3}{R}{W}", type_line="Legendary Creature — Elephant Cleric", power="4",
                  toughness="4",
                  oracle_text="Vigilance\nAt the beginning of your end step, exile target noncreature, nonland card from your "
                              "graveyard. Create a 3/2 red and white Spirit creature token.\n{1}{R}{W}, {T}, Sacrifice a Spirit: "
                              "Choose target card exiled with Quintorius. You may cast that card this turn without paying its mana "
                              "cost. If that spell would be put into a graveyard, put it on the bottom of its owner's library "
                              "instead.")
DRAW_TWO = Card(name="Study", mana_cost="{2}{U}", cmc=3.0, type_line="Sorcery", oracle_text="Draw two cards.")
CHARM = Card(name="Charm", mana_cost="{1}", cmc=1.0, type_line="Artifact")


class QuintoriusTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.quint = Permanent(QUINTORIUS)
        a.battlefield = [self.quint]
        a.library = [FOREST] * 10
        return game, a

    def end_step(self, game, a):
        fire(game, a, self.quint, "end_step")

    def spirits(self, a):
        return [p for p in a.battlefield if p.card.name == "Spirit"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(QUINTORIUS), [])

    def test_the_end_step_exiles_a_noncreature_nonland_card_and_makes_a_spirit(self):
        game, a = self.table("Study")
        a.graveyard = [DRAW_TWO, GOLEM, FOREST]
        self.end_step(game, a)
        self.assertEqual(([c.name for c in a.exile], len(self.spirits(a))), (["Study"], 1))
        self.assertEqual([c.name for c, in [(c,) for c in a.graveyard]], ["Golem", "Forest"])
        self.assertEqual([c.name for _, c in self.quint.exiled_with], ["Study"])

    def test_the_spell_is_cast_free_and_goes_to_the_bottom_of_the_library(self):
        game, a = self.table("Study", "Study")
        a.graveyard = [DRAW_TWO]
        a.battlefield += lands(3)
        self.end_step(game, a)
        before = len(a.hand)
        activate(game, a, "Choose target card exiled")
        run_stack(game)
        self.assertEqual(len(a.hand) - before, 2)  # it resolved
        self.assertEqual(([c.name for c in a.graveyard], a.library[-1].name, a.exile), ([], "Study", []))
        self.assertEqual(self.spirits(a), [])  # the Spirit was sacrificed

    def test_a_permanent_card_cast_free_enters_the_battlefield(self):
        game, a = self.table("Charm", "Charm")
        a.graveyard = [CHARM]
        a.battlefield += lands(3)
        self.end_step(game, a)
        activate(game, a, "Choose target card exiled")
        run_stack(game)
        self.assertIn("Charm", [p.card.name for p in a.battlefield])

    def test_it_needs_a_spirit_and_an_exiled_card(self):
        game, a = self.table()
        a.battlefield += lands(3)
        self.assertFalse([x for x in game.legal_actions(a) if "Choose target card exiled" in x])  # nothing exiled, no Spirit
        a.battlefield.append(Permanent(Card(name="Spirit", type_line="Token Creature — Spirit", power="3", toughness="2")))
        self.assertFalse([x for x in game.legal_actions(a) if "Choose target card exiled" in x])  # a Spirit, nothing exiled


EXCAVA = Card(name="Excava, the Risen Past", mana_cost="{2}{R}{W}", type_line="Legendary Creature — Spirit Horse", power="3", toughness="3",
              oracle_text="Flying, haste\nWhenever Excava attacks, return up to one target artifact, creature, or non-Aura "
                          "enchantment card with mana value 3 or less from your graveyard to the battlefield with a finality "
                          "counter on it. It's a 1/1 Spirit creature with flying in addition to its other types. (If a creature "
                          "with a finality counter on it would die, exile it instead.)")
BIG_GOLEM = Card(name="Big Golem", mana_cost="{4}", cmc=4.0, type_line="Artifact Creature — Golem", power="4", toughness="4")
AURA = Card(name="Boon", mana_cost="{1}{W}", cmc=2.0, type_line="Enchantment — Aura", oracle_text="Enchant creature")
SHRINE2 = Card(name="Shrine", mana_cost="{2}", cmc=2.0, type_line="Enchantment")


class ExcavaTests(unittest.TestCase):
    def attack(self, graveyard, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.excava = Permanent(EXCAVA)
        a.battlefield = [self.excava]
        a.graveyard = list(graveyard)
        fire(game, a, self.excava, "attacks")
        return game, a

    def returned(self, a):
        return [p for p in a.battlefield if p is not self.excava]

    def test_parse(self):
        self.assertEqual(unsupported_lines(EXCAVA), [])

    def test_a_card_returns_as_a_1_1_flying_spirit_with_a_finality_counter(self):
        game, a = self.attack([GOLEM], "Golem")
        [back] = self.returned(a)
        self.assertEqual((game.power(back), game.toughness(back), back.counters.get("finality")), (1, 1, 1))
        self.assertIn("Spirit", back.card.type_line)
        self.assertTrue(game.has_keyword(back, "flying"))
        self.assertIn("Artifact", back.card.type_line)  # in addition to its other types

    def test_when_it_would_die_it_is_exiled_as_the_real_card(self):
        game, a = self.attack([GOLEM], "Golem")
        [back] = self.returned(a)
        game._leave_battlefield(back, "destroyed")
        game._check_state()
        self.assertEqual(([c.name for c in a.exile], a.graveyard), (["Golem"], []))
        self.assertEqual(a.exile[0].power, "3")  # the card itself, not the 1/1

    def test_the_card_type_and_mana_value_limits(self):
        for card in (BIG_GOLEM, AURA, FOREST):
            game, a = self.attack([card], card.name)
            self.assertEqual(self.returned(a), [], card.name)

    def test_a_non_aura_enchantment_may_return(self):
        game, a = self.attack([SHRINE2], "Shrine")
        [back] = self.returned(a)
        self.assertEqual((game.power(back), "Spirit" in back.card.type_line), (1, True))

    def test_up_to_one_it_may_return_nothing(self):
        game, a = self.attack([GOLEM], "No target")
        self.assertEqual((self.returned(a), [c.name for c in a.graveyard]), ([], ["Golem"]))

    def test_an_ordinary_creature_without_a_finality_counter_goes_to_the_graveyard(self):
        game, _ = table3(pick())
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game._leave_battlefield(bear, "destroyed")
        self.assertEqual(a.exile, [])


AUGUSTA = Card(name="Augusta, Order Returned", mana_cost="{2}{W}", type_line="Legendary Creature — Spirit Advisor", power="3", toughness="3",
               oracle_text="Flying, vigilance\nWhenever Augusta attacks, each player exiles a card from their graveyard. When one or "
                           "more nonland cards are exiled this way, put that many +1/+1 counters on target attacking creature.")


class AugustaTests(unittest.TestCase):
    def attack(self, graveyards, *choices):
        """Seat A attacks with Augusta and a Bear; the targeted attacker is picked by `choices`."""
        wanted = choices[0] if choices else "Augusta"

        def policy(prompt, options):  # the first option for everything, but the creature that gets the counters
            return next((i for i, option in enumerate(options) if option.startswith(wanted)), 0) if prompt.startswith(TARGET_PROMPT) else 0
        game, _ = table3(policy, pick("Forest", "Golem"), pick("Forest", "Golem"))
        a, b, c = game.seats
        self.augusta, self.bear = Permanent(AUGUSTA), Permanent(BEAR)
        a.battlefield = [self.augusta, self.bear]
        for seat, cards in zip(game.seats, graveyards):
            seat.graveyard = list(cards)
        from infernal_machine.combat import Attack
        game.combat.attacks = [Attack(self.augusta, a, b), Attack(self.bear, a, b)]
        game.trigger("attacks", self.augusta, a)
        run_stack(game)
        return game

    def test_parse(self):
        self.assertEqual(unsupported_lines(AUGUSTA), [])

    def test_each_player_exiles_a_card_and_each_nonland_gives_a_counter(self):
        game = self.attack([[GOLEM, FOREST], [FOREST, GOLEM], [GOLEM]])
        a, b, c = game.seats
        self.assertEqual([len(s.exile) for s in game.seats], [1, 1, 1])
        total = self.augusta.counters.get("+1/+1", 0) + self.bear.counters.get("+1/+1", 0)
        self.assertEqual(total, 2)  # A and C exiled a nonland card; B chose its Forest

    def test_lands_give_no_counters(self):
        game = self.attack([[FOREST], [FOREST], [FOREST]])
        self.assertEqual(self.augusta.counters.get("+1/+1", 0) + self.bear.counters.get("+1/+1", 0), 0)
        self.assertEqual([len(s.exile) for s in game.seats], [1, 1, 1])

    def test_a_player_with_an_empty_graveyard_exiles_nothing(self):
        game = self.attack([[], [GOLEM], []])
        self.assertEqual([len(s.exile) for s in game.seats], [0, 1, 0])
        self.assertEqual(self.augusta.counters.get("+1/+1", 0) + self.bear.counters.get("+1/+1", 0), 1)

    def test_the_counters_go_on_the_chosen_attacking_creature(self):
        game = self.attack([[GOLEM], [GOLEM], []], "Bear")
        self.assertEqual((self.bear.counters.get("+1/+1"), self.augusta.counters.get("+1/+1")), (2, None))


BULL = Card(name="Renegade Bull", mana_cost="{4}{R}", type_line="Creature — Ox", power="4", toughness="4",
            oracle_text="Trample\nWhenever you cast an instant or sorcery spell, this creature gets +X/+0 until end of turn, where X "
                        "is that spell's mana value.\nWhenever this creature attacks, exile up to one target instant or sorcery card "
                        "from your graveyard and copy it. You may cast the copy without paying its mana cost.")
STUDY2 = Card(name="Study", mana_cost="{2}{U}", cmc=3.0, type_line="Sorcery", oracle_text="Draw two cards.")


class RenegadeBullTests(unittest.TestCase):
    def attack(self, graveyard, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        bull = Permanent(BULL)
        a.battlefield = [bull]
        a.graveyard = list(graveyard)
        a.library = [FOREST] * 10
        fire(game, a, bull, "attacks")
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(BULL), [])

    def test_the_card_is_exiled_and_its_copy_cast_for_free(self):
        game, a = self.attack([STUDY2], "Study", "Yes")
        self.assertEqual((len(a.hand), [c.name for c in a.exile], a.graveyard), (2, ["Study"], []))

    def test_the_copy_ceases_to_exist_rather_than_going_to_the_graveyard(self):
        game, a = self.attack([STUDY2], "Study", "Yes")
        self.assertEqual(a.graveyard, [])

    def test_the_copy_may_be_left_uncast(self):
        game, a = self.attack([STUDY2], "Study", "No")
        self.assertEqual((len(a.hand), [c.name for c in a.exile]), (0, ["Study"]))

    def test_only_an_instant_or_sorcery_can_be_chosen(self):
        game, a = self.attack([GOLEM, FOREST], "Golem")
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Golem", "Forest"], []))

    def test_up_to_one_it_may_choose_nothing(self):
        game, a = self.attack([STUDY2], "No target")
        self.assertEqual(([c.name for c in a.graveyard], a.exile, len(a.hand)), (["Study"], [], 0))
