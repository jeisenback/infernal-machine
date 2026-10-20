"""Typed prompts (prompts.py, issue #440): a prompt is still a string, and says what it is and what it is about."""

import json
import pickle
import re
import unittest
from pathlib import Path

from infernal_machine import game as game_module
from infernal_machine.game import CAST, CLONE_PROMPT, NOT_A_COPY, PASS, TARGET_PROMPT, Permanent
from infernal_machine.prompts import PRIORITY_PROMPT, Prompt, PromptKind, is_one_of, subject_of, wire_fields
from tests.helpers import BEAR, OGRE, lands, real, run_stack, table

ROOT = Path(__file__).parent.parent / "infernal_machine"
KIND = PromptKind("test_kind", "Choose a thing for ")
OTHER = PromptKind("other_kind", "Choose another thing for ")


class PromptTests(unittest.TestCase):
    def test_a_kind_is_its_text_and_a_prompt_is_the_kind_followed_by_the_subject(self):
        self.assertEqual(KIND, "Choose a thing for ")
        prompt = KIND("Clone")
        self.assertEqual(prompt, "Choose a thing for Clone")
        self.assertEqual((prompt.kind, prompt.subject), (KIND, "Clone"))
        self.assertIsInstance(prompt, str)

    def test_everything_that_treats_it_as_a_string_still_works(self):
        prompt = KIND("Clone")
        self.assertTrue(prompt.startswith(KIND))
        self.assertEqual(KIND + "Clone", prompt)
        self.assertEqual(json.loads(json.dumps({"prompt": prompt}))["prompt"], "Choose a thing for Clone")
        self.assertEqual({prompt: 1}["Choose a thing for Clone"], 1)

    def test_matches_goes_by_kind_for_a_typed_prompt(self):
        prompt = KIND("Clone")
        self.assertTrue(KIND.matches(prompt))
        self.assertFalse(OTHER.matches(prompt))

    def test_matches_goes_by_the_start_for_a_plain_string(self):
        self.assertTrue(KIND.matches("Choose a thing for Clone"))
        self.assertFalse(KIND.matches("Choose another thing for Clone"))
        self.assertFalse(KIND.matches(""))

    def test_a_typed_prompt_matches_by_the_kinds_name_so_rewording_does_not_matter(self):
        reworded = PromptKind("test_kind", "Pick a thing for ")  # the same kind, other words
        self.assertTrue(KIND.matches(reworded("Clone")))
        self.assertTrue(reworded.matches(KIND("Clone")))
        lookalike = PromptKind("lookalike", "Choose a thing for ")  # another kind that starts with the same words
        self.assertFalse(lookalike.matches(KIND("Clone")))

    def test_a_prompt_with_no_subject(self):
        prompt = KIND()
        self.assertEqual((str(prompt), prompt.subject), ("Choose a thing for ", ""))

    def test_a_subject_that_is_not_a_string_is_written_out(self):
        self.assertEqual(KIND(3), "Choose a thing for 3")

    def test_they_survive_pickling(self):
        prompt = pickle.loads(pickle.dumps(KIND("Clone")))
        self.assertEqual((str(prompt), prompt.subject, prompt.kind.name), ("Choose a thing for Clone", "Clone", "test_kind"))
        self.assertTrue(KIND.matches(prompt))


class GameTests(unittest.TestCase):
    def test_the_game_asks_with_typed_prompts(self):
        asked = []
        clone = real("Clone", "{3}{U}", "Creature — Shapeshifter", "You may have this creature enter as a copy of any creature on the battlefield.", "0", "0")

        def policy(prompt, options):
            asked.append(prompt)
            if CLONE_PROMPT.matches(prompt):
                return 0
            return next((i for i, o in enumerate(options) if o.startswith(CAST)), options.index(PASS) if PASS in options else 0)

        game, _, _ = table(policy)
        a, b = game.seats
        a.hand, a.battlefield, b.battlefield = [clone], lands(5), [Permanent(OGRE)]
        game._priority_round(a)
        run_stack(game)
        clones = [p for p in asked if isinstance(p, Prompt) and p.kind == CLONE_PROMPT]
        self.assertEqual([p.subject for p in clones], ["Clone"])
        self.assertTrue(all(isinstance(p, str) for p in asked))

    def test_a_target_prompt_names_the_spell(self):
        asked = []
        bolt = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")

        def policy(prompt, options):
            asked.append(prompt)
            return next((i for i, o in enumerate(options) if o.startswith(CAST)), options.index(PASS) if PASS in options else 0)

        game, _, _ = table(policy)
        a = game.seats[0]
        a.hand, a.battlefield = [bolt], lands(2)
        game._priority_round(a)
        targets = [p for p in asked if TARGET_PROMPT.matches(p)]
        self.assertTrue(targets and all(isinstance(p, Prompt) and p.subject == "Lightning Bolt" for p in targets))

    def test_a_policy_that_matches_by_kind_survives_rewording(self):
        reworded = PromptKind("clone", "Pick what to copy for ")  # the same kind of prompt, other words
        prompt = reworded("Clone")
        self.assertTrue(CLONE_PROMPT.matches(prompt))  # (the kind is the same: its name is "clone")
        self.assertEqual((reworded.name, CLONE_PROMPT.name), ("clone", "clone"))


class WireTests(unittest.TestCase):
    def test_a_typed_prompt_sends_its_kind_name_and_subject(self):
        self.assertEqual(wire_fields(KIND("Clone")), {"kind": "test_kind", "subject": "Clone"})
        self.assertEqual(wire_fields("Mulligan?"), {})
        self.assertEqual(wire_fields(Prompt("untyped")), {})

    def test_a_prompt_from_the_wire_matches_by_kind_whatever_its_words(self):
        prompt = Prompt.from_wire("Pick a thing for Clone", "test_kind", "Clone")
        self.assertTrue(KIND.matches(prompt))
        self.assertFalse(OTHER.matches(prompt))
        self.assertEqual(subject_of(prompt, KIND), "Clone")
        self.assertEqual(Prompt.from_wire("Choose a thing for Clone").kind, None)  # an older server: by the start of the text
        self.assertTrue(KIND.matches(Prompt.from_wire("Choose a thing for Clone")))

    def test_is_one_of_and_subject_of(self):
        self.assertTrue(is_one_of(KIND("x"), OTHER, KIND))
        self.assertFalse(is_one_of(KIND("x"), OTHER))
        self.assertEqual(subject_of(KIND("Bolt"), KIND), "Bolt")
        self.assertEqual(subject_of("Choose a thing for Bolt", KIND), "Bolt")  # a plain string: what follows the start
        self.assertEqual(subject_of(PRIORITY_PROMPT("main1"), PRIORITY_PROMPT), "main1")


class NoStringMatchingTests(unittest.TestCase):
    def test_the_engine_does_not_take_a_prompt_apart_by_its_words(self):
        pattern = re.compile(r"prompt\s*(==|!=|in)\s*[A-Z(]|prompt\.(startswith|removeprefix)\(")
        for path in ROOT.rglob("*.py"):
            if path.name == "prompts.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(pattern.search(line), f"{path.name}:{number}: {line.strip()} (use KIND.matches / subject_of)")


class EveryPromptTests(unittest.TestCase):
    def test_every_prompt_constant_is_a_kind_with_its_own_name(self):
        names = {}
        for path in ROOT.rglob("*.py"):
            module = path.read_text(encoding="utf-8")
            for match in re.finditer(r'(?m)^(\w+_PROMPT) = PromptKind\("(\w+)", ', module):
                constant, name = match.groups()
                self.assertNotIn(name, names, f"{constant} and {names.get(name)} share the kind name {name!r}")
                names[name] = constant
        self.assertGreater(len(names), 120)
        self.assertEqual(NOT_A_COPY, "Don't copy anything")  # an option, not a prompt: still a plain string

    def test_no_prompt_constant_is_a_plain_string(self):
        for path in ROOT.rglob("*.py"):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                self.assertIsNone(re.match(r'^\w+_PROMPT = ["\']', line), f"{path.name}:{number}: {line} (make it a PromptKind)")

    def test_the_game_does_not_build_a_prompt_by_adding_strings(self):
        pattern = re.compile(r"\.choose\(\s*(?:\w+\.)?\w+_PROMPT\s*\+")
        for path in ROOT.rglob("*.py"):
            self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), f"{path.name}: choose(KIND + x): call the kind, KIND(x)")

    def test_the_constants_the_game_exports_are_kinds(self):
        for name in ("CLONE_PROMPT", "TARGET_PROMPT", "X_PROMPT", "KICKER_PROMPT", "MAY_PAY_PROMPT"):
            self.assertIsInstance(getattr(game_module, name), PromptKind, name)


if __name__ == "__main__":
    unittest.main()
