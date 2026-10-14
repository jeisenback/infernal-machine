import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location("bot_strength_summary", Path(__file__).parent.parent / "tools" / "bot_strength_summary.py")
assert spec is not None and spec.loader is not None
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def shard(directory, name, wins, games, errors=0):
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"features": "attack,land", "against": "", "pod": 2, "seed": 0, "wins": wins, "games": games, "errors": errors}, f)
    return path


class SummaryTests(unittest.TestCase):
    def run_main(self, *shards):
        with tempfile.TemporaryDirectory() as d, mock.patch("builtins.print") as shown:
            code = summary.main([shard(d, f"s{i}.json", *args) for i, args in enumerate(shards)])
            return code, " ".join(str(call.args[0]) for call in shown.call_args_list)

    def test_a_stronger_bot_passes_with_the_shards_added_up(self):
        code, text = self.run_main((30, 50), (33, 48, 1))
        self.assertEqual(code, 0)
        self.assertIn("63/98", text)
        self.assertIn("No regression", text)

    def test_an_even_result_is_not_a_regression(self):
        self.assertEqual(self.run_main((25, 50))[0], 0)  # 50%, and the interval holds it

    def test_a_reliably_worse_bot_fails(self):
        code, text = self.run_main((10, 60))
        self.assertEqual(code, 1)
        self.assertIn("REGRESSION", text)

    def test_no_games_fails_and_no_files_is_a_usage_error(self):
        self.assertEqual(self.run_main((0, 0, 4))[0], 1)
        self.assertEqual(summary.main([]), 2)

    def test_it_writes_the_github_job_summary(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "summary.md")
            with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": target}), mock.patch("builtins.print"):
                summary.main([shard(d, "s.json", 30, 50)])
            self.assertIn("### Bot strength", Path(target).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
