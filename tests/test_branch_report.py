"""The branch report (tools/branch_report.py): what it prints for measurements that changed and ones that did not."""

import importlib.util
import os
import unittest

_spec = importlib.util.spec_from_file_location("branch_report", os.path.join(os.path.dirname(__file__), "..", "tools", "branch_report.py"))
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def measured(pool, templates=()):
    found = {name or "commander": ["10 decks: 5 of 10 cards fully playable (50%)"] for name in tool.FORMATS}
    return {**found, "coverage": [pool], "templates": list(templates)}


class BranchReportTests(unittest.TestCase):
    def test_a_changed_measurement_shows_before_and_after(self):
        text = tool.report(measured("10 of 20"), measured("12 of 20"), None)
        self.assertIn("- pool: 10 of 20\n  -> 12 of 20", text)
        self.assertIn("- pauper decks: 10 decks: 5 of 10 cards fully playable (50%)\n", text)  # unchanged: once, no arrow

    def test_template_lines_only_one_side_prints(self):
        text = tool.report(measured("1", ["- # `a`", "- # `b`"]), measured("1", ["- # `b`", "- # `c`"]), None)
        self.assertIn("- new: - # `c`", text)
        self.assertIn("- gone: - # `a`", text)
        self.assertNotIn("`b`", text)
        self.assertIn("no line differs", tool.report(measured("1", ["- # `a`"]), measured("1", ["- # `a`"]), None))

    def test_the_replay_is_left_out_when_not_run(self):
        self.assertNotIn("## Replay", tool.report(measured("1"), measured("1"), None))
        self.assertIn("24 of 24 games played identically", tool.report(measured("1"), measured("1"), "24 of 24 games played identically"))


if __name__ == "__main__":
    unittest.main()
