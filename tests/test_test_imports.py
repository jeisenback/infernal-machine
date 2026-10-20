"""Test files share fixtures through tests/helpers.py and never import from one another (issue #464)."""

import ast
import pathlib
import unittest

TESTS = pathlib.Path(__file__).resolve().parent


def cross_imports(source):
    """The imports of another test module in `source`, anywhere in it: (line, what)."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[:1] == ["tests"] and node.module.split(".")[-1].startswith("test_"):
                found.append((node.lineno, node.module))
            elif node.module == "tests" and any(a.name.startswith("test_") for a in node.names):
                found.append((node.lineno, "tests"))
        elif isinstance(node, ast.Import):
            found += [(node.lineno, a.name) for a in node.names if a.name.split(".")[-1].startswith("test_") and a.name.startswith("tests")]
    return found


class TestImportTests(unittest.TestCase):
    def test_the_detector_sees_every_form_of_cross_import(self):
        self.assertEqual(cross_imports("from tests.test_combat import BEAR"), [(1, "tests.test_combat")])
        self.assertEqual(cross_imports("def f():\n    from tests.test_effects import lands"), [(2, "tests.test_effects")])
        self.assertEqual(cross_imports("from tests import test_combat"), [(1, "tests")])
        self.assertEqual(cross_imports("import tests.test_combat"), [(1, "tests.test_combat")])
        self.assertEqual(cross_imports("from tests.helpers import BEAR\nfrom tests.real import REAL"), [])

    def test_no_test_file_imports_another(self):
        found = {path.name: cross_imports(path.read_text(encoding="utf-8")) for path in sorted(TESTS.glob("*.py"))}
        self.assertEqual({name: hits for name, hits in found.items() if hits}, {})


if __name__ == "__main__":
    unittest.main()
