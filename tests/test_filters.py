"""The one grammar for "which cards": every construct of `parse_filter`, with cards that must and must not match."""

import unittest

from infernal_machine.cards import Card, _mana_value
from infernal_machine.filters import matches, parse_filter


def card(type_line, cost="", colors=(), power=None, toughness=None):
    return Card(name="Test", mana_cost=cost, cmc=_mana_value(cost), type_line=type_line, oracle_text="", power=power,
                toughness=toughness, colors=colors)


BEAR = card("Creature — Bear", "{1}{G}", ("G",), "2", "2")
ELF = card("Creature — Elf Druid", "{G}", ("G",), "1", "1")
ANGEL = card("Legendary Creature — Angel", "{3}{W}{W}", ("W",), "4", "4")
LAND = card("Land")
BASIC = card("Basic Land — Forest")
ROCK = card("Artifact", "{2}")
SWORD = card("Artifact — Equipment", "{3}")
AURA = card("Enchantment — Aura", "{1}{W}", ("W",))
SAGA = card("Enchantment — Saga", "{2}{B}", ("B",))
WALKER = card("Legendary Planeswalker — Jace", "{2}{U}{U}", ("U",))
BOLT = card("Instant", "{R}", ("R",))
GOLD = card("Creature — Human", "{W}{B}", ("W", "B"), "2", "2")
TOKEN = card("Token Creature — Goblin", "", ("R",), "1", "1")
CRAB = card("Artifact Creature — Crab", "{3}", (), "3", "3")


def only(kind, *pool):
    return sorted(c.type_line for c in pool if matches(kind, c))


class Matching(unittest.TestCase):
    def test_a_type_word(self):
        self.assertTrue(matches("creature", BEAR))
        self.assertFalse(matches("creature", LAND))
        self.assertTrue(matches("land", BASIC))

    def test_a_subtype_is_any_unknown_word(self):
        self.assertTrue(matches("Elf", ELF))
        self.assertFalse(matches("Elf", BEAR))
        self.assertTrue(matches("Equipment", SWORD))
        self.assertTrue(matches("Aura", AURA))

    def test_supertype(self):
        self.assertTrue(matches("legendary creature", ANGEL))
        self.assertFalse(matches("legendary creature", BEAR))

    def test_all_words_are_needed(self):
        self.assertTrue(matches("artifact creature", CRAB))
        self.assertFalse(matches("artifact creature", ROCK))
        self.assertFalse(matches("artifact creature", BEAR))

    def test_alternatives_by_comma_and_or(self):
        kind = "artifact, creature, enchantment, or planeswalker"
        self.assertEqual(len(parse_filter(kind).alternatives), 4)
        for hit in (ROCK, BEAR, AURA, WALKER):
            self.assertTrue(matches(kind, hit))
        for miss in (LAND, BOLT):
            self.assertFalse(matches(kind, miss))
        self.assertTrue(matches("artifact or creature", BEAR))
        self.assertTrue(matches("Aura and Equipment", SWORD))

    def test_non_adjective_excludes_a_word(self):
        self.assertTrue(matches("nonland permanent", ROCK))
        self.assertFalse(matches("nonland permanent", LAND))
        self.assertTrue(matches("noncreature spell", BOLT))
        self.assertFalse(matches("noncreature spell", BEAR))
        self.assertFalse(matches("nonlegendary creature", ANGEL))
        self.assertTrue(matches("nonbasic land", LAND))
        self.assertFalse(matches("nonbasic land", BASIC))

    def test_adjectives_without_a_noun_carry_to_the_next(self):
        kind = "noncreature, nonland permanent"
        self.assertEqual(len(parse_filter(kind).alternatives), 1)
        self.assertTrue(matches(kind, SWORD))
        self.assertFalse(matches(kind, BEAR))
        self.assertFalse(matches(kind, LAND))

    def test_non_subtype(self):
        self.assertTrue(matches("non-Aura enchantment", SAGA))
        self.assertFalse(matches("non-Aura enchantment", AURA))
        self.assertFalse(matches("non-Elf creature", ELF))
        self.assertTrue(matches("non-Elf creature", BEAR))

    def test_colors_by_word_and_letter(self):
        self.assertTrue(matches("green creature", BEAR))
        self.assertFalse(matches("black creature", BEAR))
        self.assertTrue(matches("g creature", BEAR))
        self.assertTrue(matches("black creature", GOLD))  # a gold card is each of its colors
        self.assertTrue(matches("R|G", BOLT))
        self.assertTrue(matches("R|G", BEAR))
        self.assertFalse(matches("R|G", ANGEL))

    def test_nonblack(self):
        self.assertTrue(matches("nonblack creature", BEAR))
        self.assertFalse(matches("nonblack creature", GOLD))

    def test_color_count(self):
        self.assertTrue(matches("multicolored permanent", GOLD))
        self.assertFalse(matches("multicolored permanent", BEAR))
        self.assertTrue(matches("monocolored permanent", BEAR))
        self.assertFalse(matches("monocolored permanent", GOLD))
        self.assertFalse(matches("monocolored permanent", CRAB))  # colorless is not monocolored

    def test_token_and_nontoken(self):
        self.assertTrue(matches("token", TOKEN))
        self.assertFalse(matches("token", BEAR))
        self.assertTrue(matches("nontoken creature", BEAR))
        self.assertFalse(matches("nontoken creature", TOKEN))

    def test_historic(self):
        for hit in (ANGEL, WALKER, ROCK, SAGA):
            self.assertTrue(matches("historic permanent", hit), hit.type_line)
        self.assertFalse(matches("historic permanent", BEAR))

    def test_permanent_needs_a_permanent_type(self):
        self.assertTrue(matches("permanent", BEAR))
        self.assertTrue(matches("permanent", LAND))
        self.assertFalse(matches("permanent", BOLT))
        self.assertFalse(matches("nonland permanent", BOLT))

    def test_spell_and_card_name_no_type(self):
        for kind in ("spell", "card", ""):
            self.assertTrue(matches(kind, BOLT))
            self.assertTrue(matches(kind, LAND))

    def test_a_spell_suffix_is_ignored(self):
        self.assertTrue(matches("creature spell", BEAR))
        self.assertFalse(matches("creature spell", BOLT))

    def test_any_is_a_creature_or_planeswalker(self):
        self.assertEqual(only("any", BEAR, WALKER, LAND, BOLT, ROCK), ["Creature — Bear", "Legendary Planeswalker — Jace"])


class Numbers(unittest.TestCase):
    def test_mana_value_or_less(self):
        kind = "creature with mana value 2 or less"
        self.assertEqual(parse_filter(kind).mana_value, ("<=", 2))
        self.assertTrue(matches(kind, BEAR))
        self.assertTrue(matches(kind, ELF))
        self.assertFalse(matches(kind, ANGEL))

    def test_mana_value_or_greater(self):
        kind = "permanent with mana value 4 or greater"
        self.assertTrue(matches(kind, ANGEL))
        self.assertFalse(matches(kind, BEAR))

    def test_exact_mana_value(self):
        self.assertEqual(parse_filter("creature with mana value 2").mana_value, ("=", 2))
        self.assertTrue(matches("creature with mana value 2", BEAR))
        self.assertFalse(matches("creature with mana value 2", ELF))

    def test_search_form_mana_value_and_power(self):
        self.assertEqual(parse_filter("creature|mv<=3").mana_value, ("<=", 3))
        self.assertTrue(matches("creature|mv<=3", BEAR))
        self.assertFalse(matches("creature|mv<=3", ANGEL))
        self.assertTrue(matches("creature|mv>=5", ANGEL))
        self.assertFalse(matches("creature|mv>=5", BEAR))
        self.assertTrue(matches("creature|mv=2", BEAR))
        self.assertFalse(matches("creature|mv=2", ELF))
        self.assertTrue(matches("creature|p<=1", ELF))
        self.assertFalse(matches("creature|p<=1", BEAR))

    def test_power_or_less(self):
        kind = "creature with power 2 or less"
        self.assertTrue(matches(kind, BEAR))
        self.assertFalse(matches(kind, ANGEL))

    def test_power_that_is_not_a_number_does_not_match(self):
        star = card("Creature — Elemental", "{2}", (), "*", "*")
        self.assertFalse(matches("creature with power 2 or less", star))
        self.assertFalse(matches("creature with power 2 or less", BOLT))  # no power at all


class Context(unittest.TestCase):
    """Whose and what it is doing depend on the game, so the filter carries them for the caller."""

    def test_controller(self):
        self.assertEqual(parse_filter("creature an opponent controls").controller, "opponent")
        self.assertEqual(parse_filter("nonland, nontoken permanent you don't control").controller, "opponent")
        self.assertEqual(parse_filter("artifact you control").controller, "you")
        self.assertEqual(parse_filter("creature card you own").controller, "own")
        self.assertIsNone(parse_filter("creature").controller)

    def test_controller_does_not_change_what_the_card_is(self):
        self.assertTrue(matches("nonland permanent an opponent controls", ROCK))
        self.assertFalse(matches("nonland permanent an opponent controls", LAND))

    def test_state(self):
        for state in ("attacking or blocking", "tapped", "untapped", "attacking"):
            self.assertEqual(parse_filter(f"{state} creature").state, state)
        self.assertEqual(parse_filter("attacking creature an opponent controls").state, "attacking")
        self.assertEqual(parse_filter("creature").state, "")
        self.assertTrue(matches("tapped creature", BEAR))
        self.assertFalse(matches("tapped creature", LAND))

    def test_a_keyword_printed_on_the_card(self):
        flyer = Card(name="Hawk", type_line="Creature — Bird", oracle_text="Flying, vigilance", mana_cost="{1}{W}", cmc=2)
        lemur = Card(name="Lemur", type_line="Creature — Lemur", oracle_text="Flying", mana_cost="{W}", cmc=1)
        walker = Card(name="Walker", type_line="Creature — Human", oracle_text="Vigilance", mana_cost="{1}{W}", cmc=2)
        self.assertEqual(parse_filter("creature spell with flying").keyword, "flying")
        self.assertEqual([matches("creature spell with flying", c) for c in (flyer, lemur, walker)], [True, True, False])
        self.assertEqual([matches("non-Lemur creature spell with flying", c) for c in (flyer, lemur, walker)], [True, False, False])
        self.assertFalse(matches("creature with flying", BOLT), "not a creature")

    def test_a_filter_is_read_once(self):
        self.assertIs(parse_filter("creature"), parse_filter("creature"))
        self.assertEqual(parse_filter("Creature"), parse_filter("creature"))


if __name__ == "__main__":
    unittest.main()
