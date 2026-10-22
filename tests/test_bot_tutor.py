"""The "tutor" judgment (#490): when the bot searches its library or takes a card from the top, it takes the card that completes a combo
the deck holds, counting what is on its battlefield and in its hand, and otherwise its best card as before. The combos are given here as
Commander Spellbook would give them; the cards are the real Sanguine Bond and Exquisite Blood (infinite life loss), Vito and
Bloodthirsty Conqueror, and probes."""

import json
import os
import tempfile
import unittest

from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.combos import SpellbookSource
from infernal_machine.game import KEEP_ON_TOP, LOOK_PROMPT, NONE_TAKEN, PUT_ON_BOTTOM, SCRY_PROMPT, SEARCH_CARD_PROMPT, THRONE_PROMPT
from tests.helpers import COMMANDER, real

BOND = real("Sanguine Bond", "{3}{B}{B}", "Enchantment", "Whenever you gain life, target opponent loses that much life.", colors=("B",))
BLOOD = real("Exquisite Blood", "{4}{B}", "Enchantment", "Whenever an opponent loses life, you gain that much life.", colors=("B",))
CONQUEROR = real("Bloodthirsty Conqueror", "{3}{B}{B}", "Creature — Vampire Knight",
                 "Flying, deathtouch\nWhenever an opponent loses life, you gain that much life. (Damage causes loss of life.)", "5", "5",
                 colors=("B",))
BIG = real("Big Probe", "{7}", "Creature — Giant", "", "9", "9")
SMALL = real("Small Probe", "{1}", "Creature — Bear", "", "1", "1")
STUCK = real("Stuck Probe", "{2}", "Creature — Frog", "Frobnicate the widget whenever the moon is full.", "1", "1")  # a line the engine does not read
DECK = Deck([COMMANDER], [BOND, BLOOD, CONQUEROR, BIG, SMALL, STUCK], [])
COMBOS = [(BOND.name, BLOOD.name), (BOND.name, CONQUEROR.name)]
PLAIN = frozenset()


def bot(features=FEATURES, battlefield=(), hand=(), combos=COMBOS, deck=DECK):
    b = BotPlayer("Bot", deck, features=features, combos=combos)
    b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 40})
    b.notify({"event": "state", "hand": list(hand), "seats": [
        {"seat": 0, "lost": False, "battlefield": [{"name": n, "type": "Enchantment"} for n in battlefield]}]})
    return b


def taken(b, prompt, options):
    return options[b.choose(prompt, options)]


class SearchTests(unittest.TestCase):
    OPTIONS = [BIG.name, BLOOD.name, SMALL.name]

    def test_a_search_takes_the_card_that_completes_a_combo(self):
        self.assertEqual(taken(bot(battlefield=[BOND.name]), SEARCH_CARD_PROMPT, self.OPTIONS), BLOOD.name)

    def test_the_plain_bot_takes_its_most_expensive_card(self):
        self.assertEqual(taken(bot(PLAIN, battlefield=[BOND.name]), SEARCH_CARD_PROMPT, self.OPTIONS), BIG.name)
        self.assertEqual(taken(bot(FEATURES - {"tutor"}, battlefield=[BOND.name]), SEARCH_CARD_PROMPT, self.OPTIONS), BIG.name)

    def test_a_partner_in_hand_counts(self):
        self.assertEqual(taken(bot(hand=[BOND.name]), SEARCH_CARD_PROMPT, self.OPTIONS), BLOOD.name)

    def test_with_no_partner_it_takes_its_best_card_as_before(self):
        self.assertEqual(taken(bot(), SEARCH_CARD_PROMPT, self.OPTIONS), BIG.name)

    def test_a_card_that_would_only_start_a_combo_is_not_taken(self):
        self.assertEqual(taken(bot(), SEARCH_CARD_PROMPT, [BIG.name, BOND.name]), BIG.name)

    def test_any_completing_card_will_do(self):
        self.assertEqual(taken(bot(battlefield=[BOND.name]), SEARCH_CARD_PROMPT, [BIG.name, CONQUEROR.name]), CONQUEROR.name)

    def test_a_card_it_already_has_does_not_complete_anything(self):
        self.assertEqual(taken(bot(battlefield=[BOND.name, BLOOD.name]), SEARCH_CARD_PROMPT, self.OPTIONS), BIG.name)

    def test_a_look_at_the_top_takes_it_too_and_never_declines(self):
        options = [BIG.name, BLOOD.name, NONE_TAKEN]
        self.assertEqual(taken(bot(battlefield=[BOND.name]), LOOK_PROMPT, options), BLOOD.name)
        self.assertEqual(taken(bot(), LOOK_PROMPT, options), BIG.name)

    def test_other_choices_are_left_alone(self):
        self.assertEqual(taken(bot(battlefield=[BOND.name]), THRONE_PROMPT, self.OPTIONS), BIG.name)


class ComboKnowledgeTests(unittest.TestCase):
    def test_a_combo_with_a_piece_the_engine_cannot_play_is_ignored(self):
        combos = [(BOND.name, STUCK.name)]
        self.assertEqual(taken(bot(battlefield=[BOND.name], combos=combos), SEARCH_CARD_PROMPT, [BIG.name, STUCK.name]), BIG.name)

    def test_a_combo_with_a_piece_from_outside_the_deck_is_ignored(self):
        """A card taken from an opponent's deck (Plargg and Nassari cast them) is on the battlefield, but the bot can't know the engine plays it."""
        combos = [(BLOOD.name, "Borrowed Card")]
        self.assertEqual(taken(bot(battlefield=["Borrowed Card"], combos=combos), SEARCH_CARD_PROMPT, [BIG.name, BLOOD.name]), BIG.name)

    def test_a_deck_with_no_combos_is_unchanged(self):
        self.assertEqual(taken(bot(combos=[], battlefield=[BOND.name]), SEARCH_CARD_PROMPT, [BIG.name, BLOOD.name]), BIG.name)


class ScryTests(unittest.TestCase):
    """With no land in play a card that costs 5 would be sent to the bottom; one that completes a combo stays on top."""
    OPTIONS = [KEEP_ON_TOP, PUT_ON_BOTTOM]

    def test_a_completing_card_stays_on_top(self):
        self.assertEqual(bot(battlefield=[BOND.name]).choose(SCRY_PROMPT(BLOOD.name), self.OPTIONS), 0)

    def test_without_a_partner_it_goes_to_the_bottom_as_before(self):
        self.assertEqual(bot().choose(SCRY_PROMPT(BLOOD.name), self.OPTIONS), 1)

    def test_the_plain_bot_sends_it_to_the_bottom(self):
        self.assertEqual(bot(PLAIN, battlefield=[BOND.name]).choose(SCRY_PROMPT(BLOOD.name), self.OPTIONS), 1)


class CacheTests(unittest.TestCase):
    """With no combos given the bot reads them from the Commander Spellbook cache in the working directory, and only from there."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(os.chdir, self.old)

    def write_cache(self):
        variants = [{"id": "1", "uses": [{"card": {"name": n}} for n in combo], "produces": [{"feature": {"name": "Infinite life loss"}}]}
                    for combo in COMBOS]
        SpellbookSource(http=lambda request: {"results": {"identity": "B", "included": variants, "almostIncluded": []}},
                        cache_path=".cache/combos.json").find(DECK)

    def test_a_cached_answer_is_used(self):
        self.write_cache()
        self.assertEqual(taken(bot(combos=None, battlefield=[BOND.name]), SEARCH_CARD_PROMPT, [BIG.name, BLOOD.name]), BLOOD.name)

    def test_with_no_cache_the_bot_plays_as_before_and_nothing_is_written(self):
        self.assertEqual(taken(bot(combos=None, battlefield=[BOND.name]), SEARCH_CARD_PROMPT, [BIG.name, BLOOD.name]), BIG.name)
        self.assertFalse(os.path.exists(".cache"))

    def test_the_plain_bot_never_reads_the_cache(self):
        self.write_cache()
        calls = []
        original = SpellbookSource.cached
        SpellbookSource.cached = lambda self, deck: calls.append(deck) or original(self, deck)  # type: ignore[method-assign]
        self.addCleanup(setattr, SpellbookSource, "cached", original)
        bot(PLAIN, combos=None)
        self.assertEqual(calls, [])
        bot(FEATURES, combos=None)
        self.assertEqual(len(calls), 1)

    def test_a_deck_the_cache_does_not_know_gets_nothing(self):
        self.write_cache()
        other = Deck([COMMANDER], [BOND, BLOOD, BIG], [])
        self.assertEqual(taken(bot(combos=None, battlefield=[BOND.name], deck=other), SEARCH_CARD_PROMPT, [BIG.name, BLOOD.name]), BIG.name)


class CachedLookupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "combos.json")

    @staticmethod
    def no_network(request):
        raise AssertionError("the cache lookup must not ask Spellbook")

    def answer(self, *cards):
        return lambda request: {"results": {"identity": "B", "included": [{"id": "1", "uses": [{"card": {"name": n}} for n in cards]}],
                                            "almostIncluded": []}}

    def test_it_answers_from_the_cache_without_asking_spellbook(self):
        SpellbookSource(http=self.answer(BOND.name, BLOOD.name), cache_path=self.path).find(DECK)
        report = SpellbookSource(http=self.no_network, cache_path=self.path).cached(DECK)
        self.assertEqual([c.cards for c in report.included], [(BOND.name, BLOOD.name)])

    def test_it_is_none_without_an_answer_and_writes_nothing(self):
        self.assertIsNone(SpellbookSource(http=self.no_network, cache_path=self.path).cached(DECK))
        self.assertFalse(os.path.exists(self.path))
        self.assertIsNone(SpellbookSource(http=self.no_network, cache_path=None).cached(DECK))

    def test_a_changed_cache_is_read_again(self):
        source = SpellbookSource(http=self.answer(BOND.name, BLOOD.name), cache_path=self.path)
        other = Deck([COMMANDER], [BOND, BLOOD], [])
        source.find(DECK)
        self.assertIsNone(source.cached(other))  # read once, without the other deck
        source.find(other)
        self.assertEqual([c.cards for c in source.cached(other).included], [(BOND.name, BLOOD.name)])

    def test_an_older_cache_format_is_ignored(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"format": 0, "decks": {}}, f)
        self.assertIsNone(SpellbookSource(http=self.no_network, cache_path=self.path).cached(DECK))


if __name__ == "__main__":
    unittest.main()
