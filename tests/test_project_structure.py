"""Repository paths, command compatibility and modular import boundaries."""
import importlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from orie5260.paths import ROOT, DATA, OUTPUTS
from orie5260.cli import COMMANDS, resolve_command


class ProjectStructureTests(unittest.TestCase):
    def test_data_and_output_paths_are_repository_relative(self):
        self.assertEqual(ROOT, Path(__file__).resolve().parent.parent)
        self.assertEqual(DATA, ROOT / 'data')
        self.assertEqual(OUTPUTS, ROOT / 'outputs')
        self.assertTrue((DATA / 'MonthlyReturns_FullSample.xlsx').is_file())
        from orie5260.backtests import daily_baseline
        self.assertEqual(daily_baseline.ROOT, ROOT)
        self.assertEqual(daily_baseline.OUT, OUTPUTS / 'baseline')

    def test_every_command_imports_without_running_a_backtest(self):
        for name, command in COMMANDS.items():
            with self.subTest(command=name):
                module = importlib.import_module(command.module)
                self.assertTrue(callable(module.main))
                self.assertTrue(module.OUT.is_relative_to(OUTPUTS))

    def test_old_main_imports_are_the_same_module_objects(self):
        pairs = {'daily_baseline': 'orie5260.backtests.daily_baseline',
                 'run_final_strategy': 'orie5260.backtests.final_strategy',
                 'compare_baseline': 'orie5260.backtests.compare_baseline'}
        for old, new in pairs.items():
            self.assertIs(importlib.import_module(old), importlib.import_module(new))

    def test_command_aliases_and_dry_run_work_from_another_directory(self):
        self.assertEqual(resolve_command('factor_ic_analysis.py')[0], 'factor-ic')
        self.assertEqual(resolve_command('ppt-results')[0], 'selected-42')
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(ROOT / 'run.py'), 'selected-42', '--dry-run'],
                                    cwd=directory, capture_output=True, text=True, check=True)
        self.assertIn('orie5260.presentation.prepare_results', result.stdout)
        self.assertIn(str(ROOT), result.stdout)

    def test_compatibility_exports_resolve_to_real_modular_implementations(self):
        from orie5260.models.ic_feature_filter import select_inputs
        from orie5260.factors.selection import select_inputs as actual_select
        from orie5260.portfolio.engine import cost_aware_path
        from orie5260.execution.optimizer import cost_aware_path as actual_execution
        self.assertIs(select_inputs, actual_select)
        self.assertIs(cost_aware_path, actual_execution)


if __name__ == '__main__':
    unittest.main()
