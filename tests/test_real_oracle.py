"""The engine against real Oracle text.

`real_oracle_texts.json` holds the exact Oracle text of cards, copied from Scryfall, so the wording patterns are
checked against what the cards really say and not what the test author remembered (issues #25 and #50).
"""

import json
import re
import unittest
from pathlib import Path

from infernal_machine.cards import Card
from infernal_machine.effects import (Animate, Condition, Draw, LoseLife, LoseLifeEqualToManaValue, Scry,
                                      UnlessPays, activated_abilities, clone_kind, extra_votes, no_max_hand_size,
                                      replacement_effects, spell_effects, triggered_abilities)
from infernal_machine.game import HAND_SIZE, Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.undercity import ROOMS, START
from tests.helpers import BEAR, pick, table3

from tests.real import DATA, REAL  # noqa: F401  (REAL is imported from here by other tests)


class SupportTests(unittest.TestCase):
    def test_every_real_text_is_understood(self):
        for entry in DATA["cards"]:  # not "unsupported_cards": those are there to test what the report lists
            self.assertEqual(unsupported_lines(REAL[entry["name"]]), [], entry["name"])


class WordingTests(unittest.TestCase):
    def test_manlands_use_the_current_wording(self):
        for name, stats in (("Treetop Village", (3, 3)), ("Mutavault", (2, 2))):
            ability = next(a for a in activated_abilities(REAL[name]) if a.mana_cost)
            [animate] = [e for e in ability.effects if isinstance(e, Animate)]
            self.assertEqual((animate.power, animate.toughness), stats, name)

    def test_threaten(self):
        [effect] = spell_effects(REAL["Threaten"])
        self.assertEqual((effect.target, effect.until_end_of_turn, effect.untap, effect.haste),
                         ("creature", True, True, True))

    def test_clone_says_this_creature_not_its_own_name(self):
        self.assertEqual(clone_kind(REAL["Clone"]), ("creature", False))

    def test_josu_vess_says_he_was_kicked(self):
        ability = next(a for a in triggered_abilities(REAL["Josu Vess, Lich Knight"]) if a.condition)
        self.assertEqual(ability.condition, Condition("kicked"))

    def test_scry_then_draw(self):
        self.assertEqual(spell_effects(REAL["Preordain"]), [Scry(2), Draw(1)])
        self.assertEqual(spell_effects(REAL["Read the Bones"]), [Scry(2), Draw(2), LoseLife(2)])

    def test_reanimate_loses_life_equal_to_that_cards_mana_value(self):
        self.assertIsInstance(spell_effects(REAL["Reanimate"])[-1], LoseLifeEqualToManaValue)

    def test_doubling_season_names_the_permanent(self):
        found = replacement_effects(REAL["Doubling Season"])
        self.assertEqual((found.tokens, found.counters), (2, 2))

    def test_smothering_tithe_asks_the_player_to_pay(self):
        [ability] = triggered_abilities(REAL["Smothering Tithe"])
        self.assertEqual(ability.event, "opponent_draw")
        [effect] = ability.effects
        self.assertEqual((type(effect), effect.cost), (UnlessPays, "{2}"))


class BehaviourTests(unittest.TestCase):
    def test_nonblack_and_nonartifact_targets(self):
        game, _ = table3()
        a, b, _ = game.seats
        black = Card(name="Ghoul", type_line="Creature — Zombie", colors=("B",), power="1", toughness="1")
        robot = Card(name="Robot", type_line="Artifact Creature — Golem", power="1", toughness="1")
        b.battlefield = [Permanent(black), Permanent(robot), Permanent(BEAR)]
        names = lambda kind: sorted(o.card.name for _, o in game.target_options(kind, a))
        self.assertEqual(names("nonblack creature"), ["Bear", "Robot"])
        self.assertEqual(names("nonartifact creature"), ["Bear", "Ghoul"])

    def test_no_maximum_hand_size(self):
        for card, kept in ((None, HAND_SIZE), (REAL["Thought Vessel"], 9)):
            game, _ = table3(pick("Bear"))
            a = game.seats[0]
            a.hand = [BEAR] * 9
            a.battlefield = [Permanent(card)] if card else []
            game.step = "cleanup"
            game._turn_based_actions(a)
            self.assertEqual(len(a.hand), kept)
        self.assertTrue(no_max_hand_size(REAL["Reliquary Tower"]))

    def test_tivit_lets_its_controller_vote_twice(self):
        tivit = Card(name="Tivit", type_line="Legendary Creature — Sphinx Rogue",
                     oracle_text=REAL["Tivit, Seller of Secrets"].oracle_text)
        self.assertEqual(extra_votes(tivit), 1)
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(tivit)]
        self.assertEqual(sum(game.vote(a, ["evidence", "bribery"])), 4)  # three players, one voting twice
        a.battlefield = []
        self.assertEqual(sum(game.vote(a, ["evidence", "bribery"])), 3)


class ScryfallDataTests(unittest.TestCase):
    """Card.from_scryfall on a real Scryfall object (a modal double-faced Pathway), not a hand-made one."""

    def test_a_pathway(self):
        data = json.loads((Path(__file__).parent / "pathway_scryfall.json").read_text(encoding="utf-8"))
        card = Card.from_scryfall(data)
        self.assertEqual((card.name, card.type_line, card.oracle_text), (data["name"], "Land", "{T}: Add {U}."))
        self.assertEqual(card.produced_mana, ("U",))  # the front face makes only blue
        self.assertEqual((card.back.name, card.back.type_line, card.back.oracle_text),
                         ("Lavaglide Pathway", "Land", "{T}: Add {R}."))
        self.assertEqual(card.back.produced_mana, ("R",))
        self.assertTrue(card.legal_in("commander"))
        self.assertEqual(card.color_identity, ("R", "U"))


class UndercityTests(unittest.TestCase):
    """Every room's text and exits against the real Undercity dungeon (issue #50)."""

    def test_rooms_match_the_dungeon(self):
        real = {}
        for line in DATA["undercity"].splitlines():
            if m := re.fullmatch(r"(.+?) — (.+?)(?: \(Leads to: (.+)\))?", line):
                real[m[1]] = (m[2], tuple(m[3].split(", ")) if m[3] else ())
        self.assertEqual(len(real), 9)
        self.assertEqual(set(real), set(ROOMS))
        for name, (text, leads_to) in real.items():
            self.assertEqual(ROOMS[name].leads_to, leads_to, name)
            if name != "Throne of the Dead Three":  # the engine does this room itself (effects.ThroneOfTheDeadThree)
                self.assertEqual(ROOMS[name].text, text, name)
        self.assertEqual(START, "Secret Entrance")

    def test_the_throne(self):
        text = DATA["undercity"].splitlines()[-1]
        self.assertIn("Reveal the top ten cards of your library", text)
        self.assertIn("three +1/+1 counters", text)
        self.assertIn("hexproof until your next turn", text)
        self.assertEqual(sum(len(r.leads_to) for r in ROOMS.values()), 12)  # a 1-2-3-2-1 dungeon has 12 connections


if __name__ == "__main__":
    unittest.main()
