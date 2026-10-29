"""The tracked-decks workflow (#476): what it must keep doing, checked on its text (there is no YAML parser in the standard library)."""

import re
import unittest
from pathlib import Path

WORKFLOWS = Path(__file__).parent.parent / ".github" / "workflows"
TEXT = (WORKFLOWS / "tracked-decks.yml").read_text(encoding="utf-8")


def step(name_start):
    """The text of the step whose name starts with `name_start`, up to the next step."""
    steps = re.split(r"(?m)^      - ", TEXT)
    found = [s for s in steps if s.startswith(f"name: {name_start}")]
    assert len(found) == 1, name_start
    return found[0]


class TriggerTests(unittest.TestCase):
    def test_it_runs_on_pull_requests_that_touch_the_engine_weekly_and_by_hand(self):
        head = TEXT.split("jobs:")[0]
        self.assertIn("pull_request:", head)
        self.assertIn('"infernal_machine/**"', head)
        self.assertIn('"examples/decks/**"', head)
        self.assertIn("schedule:", head)
        self.assertIn("workflow_dispatch:", head)

    def test_the_week_and_the_card_file_cache_are_the_ones_the_other_workflows_use(self):
        self.assertIn("oracle-bulk-${{ steps.week.outputs.week }}", TEXT)
        self.assertIn("path: .cache/oracle_bulk.json", TEXT)


class AuditStepTests(unittest.TestCase):
    def test_it_checks_every_deck_against_the_baseline(self):
        run = step("The tracked decks against their baseline")
        self.assertIn("--decks examples/decks/*.txt", run)
        self.assertIn("--baseline examples/decks/baseline.json", run)

    def test_its_exit_status_survives_the_pipe_to_tee(self):
        run = step("The tracked decks against their baseline")
        self.assertIn("shell: bash", run, "bash -eo pipefail, so a failing audit is not hidden by tee")
        self.assertIn("| tee decks.md", run)

    def test_it_does_not_fail_on_its_own_so_the_table_is_still_posted(self):
        self.assertIn("continue-on-error: true", step("The tracked decks against their baseline"))
        self.assertIn("id: decks", step("The tracked decks against their baseline"))

    def test_the_last_step_fails_the_job_when_the_audit_failed(self):
        last = step("Fail if a tracked deck got worse")
        self.assertIn("always()", last)
        self.assertIn("steps.decks.outcome == 'failure'", last)
        self.assertIn("exit 1", last)

    def test_nothing_swallows_a_failure(self):
        self.assertNotIn("|| true", TEXT)
        self.assertEqual(TEXT.count("continue-on-error"), 3, "only on the three audit steps, whose results the last step turns into the job's")


class StandardStepTests(unittest.TestCase):
    """The Standard decks (#521) are checked the same way, against their own baseline, whatever Commander's verdict was."""

    NAME = "The tracked Standard decks against their baseline"

    def test_it_checks_every_standard_deck_against_the_standard_baseline(self):
        run = step(self.NAME)
        self.assertIn("--decks examples/decks/standard/*.txt", run)
        self.assertIn("--baseline examples/decks/standard/baseline.json", run)
        self.assertIn("if: always()", run, "Commander's failure must not skip Standard's check")

    def test_its_exit_status_survives_the_pipe_to_tee_and_does_not_fail_on_its_own(self):
        run = step(self.NAME)
        self.assertIn("shell: bash", run)
        self.assertIn("| tee standard.md", run)
        self.assertIn("continue-on-error: true", run)
        self.assertIn("id: standard", run)

    def test_the_last_step_fails_the_job_when_the_standard_audit_failed(self):
        self.assertIn("steps.standard.outcome == 'failure'", step("Fail if a tracked deck got worse"))

    def test_the_comment_and_the_summary_carry_both(self):
        self.assertIn("standard.md", step("Show it in the job summary"))
        self.assertIn("standard.md", step("Keep one comment on the roadmap epic up to date"))


FORMATS = ("pauper", "pioneer", "modern", "legacy", "vintage")


class OtherFormatsStepTests(unittest.TestCase):
    """The Pauper, Pioneer, Modern, Legacy and Vintage decks (#522) are checked the same way, each against its own baseline."""

    NAME = "The tracked decks of the other constructed formats against their baselines"

    def test_it_checks_every_format_against_its_own_baseline_whatever_the_others_said(self):
        run = step(self.NAME)
        self.assertIn(f"for format in {' '.join(FORMATS)}; do", run)
        self.assertIn("--decks examples/decks/$format/*.txt --baseline examples/decks/$format/baseline.json", run)
        self.assertIn("if: always()", run)
        for fmt in FORMATS:
            self.assertTrue((WORKFLOWS.parent.parent / "examples" / "decks" / fmt / "baseline.json").exists(), fmt)

    def test_one_format_getting_worse_fails_the_step_and_the_rest_still_run(self):
        run = step(self.NAME)
        self.assertIn("shell: bash", run, "bash -eo pipefail, so a failing audit is not hidden by tee")
        self.assertIn("| tee $format.md || status=1", run, "a failure is remembered and the loop goes on")
        self.assertIn("exit $status", run)
        self.assertIn("continue-on-error: true", run)
        self.assertIn("id: formats", run)

    def test_the_last_step_fails_the_job_when_a_format_got_worse(self):
        self.assertIn("steps.formats.outcome == 'failure'", step("Fail if a tracked deck got worse"))

    def test_the_summary_has_their_tables_and_the_comment_their_headlines(self):
        self.assertIn("cat $format.md", step("Show it in the job summary"))
        comment = step("Keep one comment on the roadmap epic up to date")
        self.assertIn("head -1 $format.md", comment, "one line each, so the comment stays under GitHub's limit")


class MisparseAuditStepTests(unittest.TestCase):
    NAME = "No card is read in a way the audit knows is wrong"

    def test_the_audit_runs_over_the_card_file_even_when_the_decks_check_failed(self):
        run = step(self.NAME)
        self.assertIn("python tools/explain_card.py --audit", run)
        self.assertIn("if: always()", run)

    def test_its_exit_status_survives_the_pipe_to_tee(self):
        run = step(self.NAME)
        self.assertIn("| tee -a", run)
        self.assertIn("shell: bash", run, "bash -eo pipefail, so a finding is not hidden by tee")

    def test_its_failure_is_the_jobs_failure(self):
        self.assertNotIn("continue-on-error", step(self.NAME))

    def test_a_change_to_the_tool_runs_the_workflow(self):
        self.assertIn('"tools/explain_card.py"', TEXT.split("jobs:")[0])


class CommentStepTests(unittest.TestCase):
    def test_a_pull_request_never_posts_the_comment(self):
        self.assertIn("github.event_name != 'pull_request'", step("Keep one comment on the roadmap epic up to date"))

    def test_the_comment_is_kept_up_to_date_and_not_added_every_week(self):
        run = step("Keep one comment on the roadmap epic up to date")
        self.assertIn("<!-- tracked-decks -->", run)
        self.assertIn("-X PATCH", run)
        self.assertIn("gh issue comment", run)
        self.assertEqual(run.count("head -c 30000"), 2, "Commander's and Standard's halves: GitHub refuses a comment over 65536 characters")

    def test_the_comment_failing_is_not_ignored(self):
        self.assertNotIn("continue-on-error", step("Keep one comment on the roadmap epic up to date"))

    def test_it_posts_on_the_roadmap_epic(self):
        self.assertIn('EPIC: "453"', TEXT)


class PermissionTests(unittest.TestCase):
    def test_only_this_job_may_write_issues_and_only_to_post_the_comment(self):
        self.assertEqual(len(re.findall(r"issues: write", TEXT)), 1)
        self.assertIn("contents: read", TEXT.split("jobs:")[0], "read-only by default")
        for path in WORKFLOWS.glob("*.yml"):
            if path.name != "tracked-decks.yml":
                self.assertNotIn("issues: write", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()
