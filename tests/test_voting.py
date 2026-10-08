import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import Vote, VoteToExile, spell_effects, triggered_abilities, ward_cost
from infernal_machine.game import VOTE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, creature
from tests.test_effects import FOREST
from tests.test_mass_effects import table3

PLEA = Card(name="Plea for Power", mana_cost="{3}{U}", type_line="Sorcery",
            oracle_text="Will of the council — Starting with you, each player votes for time or knowledge. If time gets more "
                        "votes, take an extra turn after this one. If knowledge gets more votes or the vote is tied, draw "
                        "three cards.")
TIVIT = REAL["Tivit, Seller of Secrets"]
JUDGMENT = Card(name="Council's Judgment", mana_cost="{1}{W}{W}", type_line="Sorcery",
                oracle_text="Will of the council — Starting with you, each player votes for a nonland permanent you don't "
                            "control. Exile each permanent with the most votes or tied for most votes.")
OGRE = creature("Ogre", 3, 3)


def votes(*words):
    """Policy: seats vote in turn (one word each, by option text); anything else takes the first option."""
    remaining = iter(words)
    return lambda prompt, options: options.index(next(remaining)) if prompt.startswith(VOTE_PROMPT) else 0


def seat_votes(*choices):
    """Each seat answers vote prompts from its own list of option numbers."""
    return [lambda prompt, options, c=iter(c): next(c) if prompt.startswith(VOTE_PROMPT) else 0 for c in choices]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        self.assertEqual(unsupported_lines(PLEA) + unsupported_lines(TIVIT) + unsupported_lines(JUDGMENT), [])
        self.assertIsInstance(spell_effects(PLEA)[0], Vote)
        self.assertEqual(spell_effects(JUDGMENT), [VoteToExile()])
        self.assertIsInstance(triggered_abilities(TIVIT)[0].effects[0], Vote)

    def test_half_a_vote_is_not_understood(self):
        for text in ("Starting with you, each player votes for time or knowledge.",
                     "If time gets more votes, draw a card.",
                     "Starting with you, each player votes for a nonland permanent you don't control.",
                     "Starting with you, each player votes for time or knowledge. If doom gets more votes, draw a card.",
                     "Starting with you, each player votes for time or knowledge. If time gets more votes, destroy target "
                     "creature."):
            card = Card(name="Half", mana_cost="{U}", type_line="Sorcery", oracle_text=text)
            self.assertIsNone(spell_effects(card), text)


class VoteTests(unittest.TestCase):
    def test_the_majority_wins(self):
        game, _ = table3(*seat_votes([0], [0], [1]))  # time, time, knowledge
        a = game.seats[0]
        spell_effects(PLEA)[0].resolve(game, a, None)
        self.assertEqual((game.extra_turns, a.hand), ([0], []))

    def test_a_tie_goes_to_the_side_that_says_so(self):
        game, _ = table3(*seat_votes([0], [1], [1]))
        game.seats[1].library = []
        a = game.seats[0]
        a.library = [FOREST] * 5
        spell_effects(PLEA)[0].resolve(game, a, None)  # time 1, knowledge 2: knowledge wins
        self.assertEqual(len(a.hand), 3)
        game, _ = table3(*seat_votes([0], [1]))
        game.seats[2].lost = True  # two voters left, one each: a tie
        a = game.seats[0]
        a.library = [FOREST] * 5
        spell_effects(PLEA)[0].resolve(game, a, None)
        self.assertEqual((game.extra_turns, len(a.hand)), ([], 3))

    def test_tivit_votes_on_entering_and_on_combat_damage(self):
        events = sorted(a.event for a in triggered_abilities(TIVIT))
        self.assertEqual(events, ["combat_damage_to_player", "enters"])
        self.assertEqual(ward_cost(TIVIT), "{3}")

    def test_voting_starts_with_the_caster_and_is_public(self):
        game, players = table3(lambda prompt, options: 0)
        b = game.seats[1]
        b.library = [FOREST] * 5
        spell_effects(PLEA)[0].resolve(game, b, None)
        order = [e["seat"] for e in players[0].events if e["event"] == "vote"]
        self.assertEqual(order, [1, 2, 0])
        self.assertEqual(next(e for e in players[2].events if e["event"] == "vote")["choice"], "time")

    def test_a_vote_that_counts_each_vote(self):
        game, _ = table3(*seat_votes([0], [0], [1]))  # evidence, evidence, bribery
        a = game.seats[0]
        triggered_abilities(TIVIT)[0].effects[0].resolve(game, a, None)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Clue", "Clue", "Treasure"])

    def test_a_dead_player_does_not_vote(self):
        game, players = table3(lambda prompt, options: 0)
        game.seats[2].lost = True
        game.vote(game.seats[0], ["x", "y"])
        self.assertEqual([e["seat"] for e in players[0].events if e["event"] == "vote"], [0, 1])


class VoteToExileTests(unittest.TestCase):
    def setUp(self):
        self.game, self.players = table3(*seat_votes([0], [0], [1]))
        self.a, self.b, self.c = self.game.seats
        self.bear, self.ogre = Permanent(BEAR), Permanent(OGRE)
        self.b.battlefield = [self.bear, Permanent(FOREST)]
        self.c.battlefield = [self.ogre]
        self.a.battlefield = [Permanent(BEAR)]

    def test_only_nonland_permanents_the_caster_does_not_control(self):
        self.game.vote_to_exile(self.a)
        options = next(o for p, o in self.players[0].prompts if p.startswith(VOTE_PROMPT))
        self.assertEqual(len(options), 2)
        self.assertTrue(all("Forest" not in o and "seat 0" not in o for o in options))

    def test_the_most_voted_is_exiled(self):
        self.game.vote_to_exile(self.a)  # bear, bear, ogre
        self.assertEqual(([p.card.name for p in self.b.battlefield], len(self.c.battlefield)), (["Forest"], 1))
        self.assertEqual([c.name for c in self.b.exile], ["Bear"])

    def test_tied_permanents_are_all_exiled(self):
        game, _ = table3(*seat_votes([0], [1], [2]))  # three players, three different permanents
        a, b, c = game.seats
        b.battlefield, c.battlefield = [Permanent(BEAR), Permanent(OGRE)], [Permanent(OGRE)]
        game.vote_to_exile(a)
        self.assertEqual((len(b.battlefield), len(c.battlefield)), (0, 0))

    def test_a_clear_winner_is_the_only_one_exiled(self):
        game, _ = table3(*seat_votes([0], [1], [1]))
        a, b, c = game.seats
        b.battlefield, c.battlefield = [Permanent(BEAR)], [Permanent(OGRE)]
        game.vote_to_exile(a)  # bear, ogre, ogre
        self.assertEqual((len(b.battlefield), len(c.battlefield)), (1, 0))

    def test_nothing_to_vote_for(self):
        game, players = table3()
        game.vote_to_exile(game.seats[0])
        self.assertFalse([e for e in players[0].events if e["event"] == "vote"])

    def test_bots_vote_against_an_opponents_permanent(self):
        bot = BotPlayer("B", Deck([FOREST], [], []))
        bot._seat = 1
        options = ["Bear 2/2 (seat 1, #1)", "Ogre 3/3 (seat 2, #1)"]
        self.assertEqual(bot.choose(VOTE_PROMPT + "Council's Judgment", options), 1)
        self.assertEqual(bot.choose(VOTE_PROMPT + "Plea for Power", ["time", "knowledge"]), 0)


CAPITAL_PUNISHMENT = REAL["Capital Punishment"]
class PerVoteEffectsTests(unittest.TestCase):
    def test_parse(self):
        [vote] = spell_effects(CAPITAL_PUNISHMENT)
        self.assertEqual([(o.kind, o.option) for o in vote.outcomes], [("each", "death"), ("each", "taxes")])
        self.assertEqual(unsupported_lines(CAPITAL_PUNISHMENT), [])

    def test_an_outcome_that_isnt_understood_spoils_the_card(self):
        card = Card(name="Odd", mana_cost="{B}", type_line="Sorcery",
                    oracle_text="Starting with you, each player votes for death or taxes. Each opponent sacrifices a creature "
                                "for each death vote and flies away for each taxes vote.")
        self.assertIsNone(spell_effects(card))

    def test_each_opponent_loses_a_creature_per_death_vote_and_a_card_per_taxes_vote(self):
        game, _ = table3(*seat_votes([0], [0], [1]))  # death, death, taxes
        a, b, c = game.seats
        for seat in (b, c):
            seat.battlefield = [Permanent(BEAR) for _ in range(3)]
            seat.hand = [BEAR, BEAR, BEAR]
        a.battlefield, a.hand = [Permanent(BEAR)], [BEAR]
        spell_effects(CAPITAL_PUNISHMENT)[0].resolve(game, a, None)
        self.assertEqual([len(s.battlefield) for s in game.seats], [1, 1, 1])  # two death votes: two creatures each
        self.assertEqual([len(s.hand) for s in game.seats], [1, 2, 2])  # one taxes vote: one card each
        self.assertEqual(len(a.graveyard), 0)

    def test_an_opponent_with_nothing_to_lose_loses_nothing(self):
        game, _ = table3(*seat_votes([0], [0], [0]))
        a, b, c = game.seats
        b.battlefield, c.battlefield = [Permanent(BEAR)], []
        spell_effects(CAPITAL_PUNISHMENT)[0].resolve(game, a, None)
        self.assertEqual((len(b.battlefield), len(c.battlefield)), (0, 0))
