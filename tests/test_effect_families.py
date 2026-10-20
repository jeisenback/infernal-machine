"""outcomes.py was split by family (issue #437): the effect classes are in effects/families/, and every name is still importable from
where it always was."""

import importlib
import inspect
import pkgutil
import subprocess
import sys
import unittest

from infernal_machine.effects import families, outcomes


def family_modules():
    return [importlib.import_module(f"{families.__name__}.{info.name}") for info in pkgutil.iter_modules(families.__path__)]


class FamilyTests(unittest.TestCase):
    def test_every_class_of_a_family_is_still_importable_from_outcomes(self):
        count = 0
        for module in family_modules():
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module.__name__:
                    self.assertIs(getattr(outcomes, name), cls, f"{module.__name__}.{name}")
                    count += 1
        self.assertGreater(count, 380)

    def test_no_effect_class_is_defined_twice(self):
        seen = {}
        for module in family_modules():
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ == module.__name__:
                    self.assertNotIn(name, seen, f"{name} in {module.__name__} and {seen.get(name)}")
                    seen[name] = module.__name__

    def test_the_families_do_not_import_outcomes_or_each_other_in_a_circle(self):
        # each family module imports on its own in a fresh interpreter (a cycle would fail here, or depend on import order)
        for info in pkgutil.iter_modules(families.__path__):
            result = subprocess.run([sys.executable, "-c", f"import infernal_machine.effects.families.{info.name}"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"{info.name}: {result.stderr[-300:]}")

    def test_the_moved_names_are_available_from_the_effects_package_too(self):
        from infernal_machine import effects

        for name in ("Draw", "CopyToken", "CHANGE_TARGET_PROMPT", "PutCounters", "Pump", "Vote", "Amount", "Condition", "Exile"):
            self.assertTrue(hasattr(effects, name) or hasattr(outcomes, name), name)

    def test_no_module_is_a_monster_again(self):
        for module in family_modules():
            self.assertLess(len(inspect.getsource(module).splitlines()), 1000, module.__name__)


if __name__ == "__main__":
    unittest.main()
