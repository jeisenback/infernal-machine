"""The README is an overview and the pages in docs/ hold the reference (#388): the links between them must keep working."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
PAGES = sorted((ROOT / "docs").glob("*.md"))
FILES = [ROOT / "README.md", ROOT / "CLAUDE.md", *PAGES]
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading: str) -> str:
    """The anchor GitHub makes from a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    return re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text))


def headings(path: Path) -> set[str]:
    found, fenced = set(), False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            found.add(slug(line.lstrip("#")))
    return found


def links(path: Path) -> list[tuple[str, str]]:
    """(target file, anchor) for each relative link in the page; an empty file means the page itself."""
    found = []
    for target in LINK.findall(path.read_text(encoding="utf-8")):
        if re.match(r"[a-z]+:", target):
            continue  # a web address
        file, _, anchor = target.partition("#")
        found.append((file, anchor))
    return found


FLAG = re.compile(r"(?<![\w-])--[a-z][\w-]*")


def commands(path: Path) -> list[tuple[str, set[str], str]]:
    """(module, the --flags on the command line and its continuation lines, the line) for each `python -m infernal_machine.X` in a code block."""
    found, fenced, lines = [], False, path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        elif fenced and (m := re.match(r"python3? -m (infernal_machine\.\w+)", line)):
            text, j = line, i + 1
            while j < len(lines) and lines[j][:1] in (" ", "	") and not lines[j].startswith("  -"):  # (continuation lines are indented)
                text, j = text + " " + lines[j], j + 1
            found.append((m[1], set(FLAG.findall(text)), line))
    return found


class LinkTests(unittest.TestCase):
    def test_there_are_pages(self):
        self.assertGreaterEqual(len(PAGES), 7)

    def test_every_relative_link_leads_somewhere(self):
        for path in FILES:
            for file, anchor in links(path):
                target = (path.parent / file).resolve() if file else path
                self.assertTrue(target.exists(), f"{path.name} links to {file or '(itself)'}#{anchor}, which does not exist")
                if anchor and target.suffix == ".md":
                    self.assertIn(anchor, headings(target), f"{path.name} links to {target.name}#{anchor}, which is not a heading there")

    def test_every_page_is_reachable_from_the_readme(self):
        linked = {(ROOT / file).resolve() for file, _ in links(ROOT / "README.md") if file}
        for page in PAGES:
            self.assertIn(page.resolve(), linked, f"docs/{page.name} is not linked from README.md")

    def test_every_page_has_a_title(self):
        for page in PAGES:
            self.assertTrue(page.read_text(encoding="utf-8").startswith("# "), page.name)

    def test_the_readme_stays_an_overview(self):
        self.assertLess(len((ROOT / "README.md").read_text(encoding="utf-8").splitlines()), 150)

    def test_claude_md_sends_new_card_effects_to_the_page_that_holds_them(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        match = re.search(r"Add a bullet to `(docs/[\w-]+\.md)`", text)
        self.assertIsNotNone(match, "CLAUDE.md no longer says where to add the card-effects bullet")
        assert match is not None
        page = ROOT / match.group(1)
        self.assertTrue(page.exists())
        self.assertIn("card-effects", headings(page))  # the "## Card effects" section is in that page

    def test_the_commands_in_the_docs_exist_and_take_the_flags_they_show(self):
        helps: dict[str, str] = {}
        checked = 0
        for path in FILES:
            for module, flags, line in commands(path):
                if not flags:
                    continue
                if module not in helps:
                    run = subprocess.run([sys.executable, "-m", module, "--help"], capture_output=True, text=True, cwd=ROOT)
                    helps[module] = run.stdout
                    self.assertEqual(run.returncode, 0, f"{module} --help failed: {run.stderr[-200:]}")
                for flag in flags - {"--help"}:
                    self.assertIn(flag, helps[module], f"{path.name}: `{line.strip()}` uses {flag}, which {module} does not take")
                checked += 1
        self.assertGreater(checked, 8)  # (the walkthrough and the reference show plenty of commands with flags)

    def test_the_slug_matches_github(self):
        self.assertEqual(slug("The card caches"), "the-card-caches")
        self.assertEqual(slug("What the engine can't play yet"), "what-the-engine-cant-play-yet")
        self.assertEqual(slug("Quick start: play a game"), "quick-start-play-a-game")


if __name__ == "__main__":
    unittest.main()
