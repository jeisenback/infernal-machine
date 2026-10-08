import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import CLUE, TREASURE, CreateTokens, TargetControllerCreatesTokens, spell_effects
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import attack_all
from tests.test_effects import BOLT, FOREST, lands, pick, table

RAISE = Card(name="Raise the Alarm", mana_cost="{1}{W}", type_line="Instant",
             oracle_text="Create two 1/1 white Soldier creature tokens.")
BEAST_WITHIN = Card(name="Beast Within", mana_cost="{2}{G}", type_line="Instant",
                    oracle_text="Destroy target permanent. Its controller creates a 3/3 green Beast creature token.")
SMOTHERING = REAL["Smothering Tithe"]
INVESTIGATOR = Card(name="Investigator", mana_cost="{1}{U}", type_line="Creature — Human", power="1", toughness="1",
                    oracle_text="When this creature enters, create a Clue token.")
OGRE = Card(name="Ogre", mana_cost="{3}", type_line="Creature — Ogre", power="3", toughness="3")
DRAKE = Card(name="Drake", mana_cost="{R}", type_line="Creature — Drake", power="2", toughness="2")
MARTYR_TOKEN_MAKER = Card(name="Hatchery", mana_cost="{1}", type_line="Artifact",
                          oracle_text="{T}: Create a 1/1 black Rat creature token with deathtouch.")


def tokens(seat):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token")]


class ParseTests(unittest.TestCase):
    def test_creature_tokens(self):
        [effect] = spell_effects(RAISE)
        self.assertEqual((effect.count, effect.token.name, effect.token.power, effect.token.colors),
                         (2, "Soldier", "1", ("W",)))
        thopter = spell_effects(Card(name="x", oracle_text="Create a 1/1 colorless Thopter artifact creature token with flying."))[0]
        self.assertEqual((thopter.token.type_line, thopter.token.oracle_text), ("Token Artifact Creature — Thopter", "Flying"))
        knight = spell_effects(Card(name="x", oracle_text="Create a 2/2 black and red Knight creature token with menace, trample, and haste."))[0]
        self.assertEqual((knight.token.colors, knight.token.oracle_text), (("B", "R"), "Menace, trample, haste"))

    def test_named_tokens_and_follow_up(self):
        self.assertEqual(spell_effects(Card(name="x", oracle_text="Create two Treasure tokens.")), [CreateTokens(2, TREASURE)])
        self.assertIsInstance(spell_effects(BEAST_WITHIN)[1], TargetControllerCreatesTokens)

    def test_unsupported_tokens(self):
        self.assertIsNone(spell_effects(Card(name="x", oracle_text="Create a token that's a copy of target creature, "
                                                                  "except it's a 1/1.")))
        quoted = 'Create a 1/1 green Saproling creature token with "This creature gets +1/+1."'
        self.assertIsNone(spell_effects(Card(name="x", oracle_text=quoted)))

    def test_report_counts_token_makers_as_playable(self):
        for card in (RAISE, BEAST_WITHIN, SMOTHERING, INVESTIGATOR, MARTYR_TOKEN_MAKER, TREASURE, CLUE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class TokenTests(unittest.TestCase):
    def test_create_creature_tokens(self):
        game, a, _ = table(pick(CAST))
        game.seats[0].hand = [RAISE]
        game.seats[0].battlefield = lands(2)
        game._priority_round(game.seats[0])
        made = tokens(game.seats[0])
        self.assertEqual([(t.card.name, t.sick) for t in made], [("Soldier", True), ("Soldier", True)])
        self.assertEqual(sum(e["event"] == "token_created" for e in a.events), 2)

    def test_beast_within_gives_the_token_to_the_targets_controller(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        game.seats[0].hand = [BEAST_WITHIN]
        game.seats[0].battlefield = lands(3)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual([p.card.name for p in game.seats[1].battlefield], ["Beast"])
        self.assertEqual(tokens(game.seats[0]), [])

    def test_tokens_stop_existing_when_they_leave(self):
        game, _, _ = table(pick(CAST, "Soldier"))
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1)
        game.create_tokens(game.seats[1], spell_effects(RAISE)[0].token, 1)
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].battlefield, game.seats[1].graveyard), ([], []))

    def test_token_creatures_can_attack_next_turn(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        game.create_tokens(a, spell_effects(RAISE)[0].token, 2)
        game.turn = 3
        game._take_turn(a)
        self.assertEqual(game.seats[1].life, 38)

    def test_treasure_pays_and_is_sacrificed_last(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [DRAKE]
        seat.battlefield = [Permanent(FOREST)]
        game.create_tokens(seat, TREASURE, 1)
        self.assertIn(CAST + "Drake", game.legal_actions(seat))  # {R}: only the Treasure makes red
        game._priority_round(seat)
        self.assertEqual([p.card.name for p in seat.battlefield], ["Forest", "Drake"])
        self.assertEqual(seat.graveyard, [])  # the Treasure is gone, not in the graveyard

    def test_lands_are_used_before_treasure(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [Card(name="Relic", mana_cost="{1}", type_line="Artifact")]
        seat.battlefield = [Permanent(FOREST)]
        game.create_tokens(seat, TREASURE, 1)
        game._priority_round(seat)
        self.assertIn("Treasure", [p.card.name for p in seat.battlefield])

    def test_a_clue_is_cracked_for_a_card(self):
        game, _, _ = table(pick(ACTIVATE))
        seat = game.seats[0]
        seat.battlefield = lands(2)
        game.create_tokens(seat, CLUE, 1)
        game.turn = 3
        game._take_turn(seat)
        self.assertNotIn("Clue", [p.card.name for p in seat.battlefield])  # cracked for a card
        self.assertEqual(len(seat.hand), 2)  # draw step + Clue

    def test_enters_trigger_makes_a_token(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [INVESTIGATOR]
        game.seats[0].battlefield = lands(2)
        game._priority_round(game.seats[0])
        self.assertEqual([t.card.name for t in tokens(game.seats[0])], ["Clue"])


if __name__ == "__main__":
    unittest.main()
