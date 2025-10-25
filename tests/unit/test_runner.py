"""Unit tests for test runner scripts.

This module tests the test runner functions that are used by poetry scripts
to execute different types of tests.
"""

import unittest
from unittest.mock import Mock, patch

from tests import run_tests


class TestRunCommandFunction(unittest.TestCase):
    """Tests for the run_command helper function."""

    def test_run_command_exists(self):
        """Test that run_command function exists."""
        self.assertTrue(hasattr(run_tests, "run_command"))
        self.assertTrue(callable(run_tests.run_command))

    @patch("tests.run_tests.subprocess.run")
    def test_run_command_executes_subprocess(self, mock_run):
        """Test that run_command executes subprocess.run."""
        mock_run.return_value = Mock(returncode=0)

        result = run_tests.run_command("echo test")

        mock_run.assert_called_once()
        self.assertEqual(result, 0)

    @patch("tests.run_tests.subprocess.run")
    def test_run_command_uses_shell_true(self, mock_run):
        """Test that run_command uses shell=True."""
        mock_run.return_value = Mock(returncode=0)

        run_tests.run_command("echo test")

        # Check that shell=True was passed
        call_kwargs = mock_run.call_args[1]
        self.assertTrue(call_kwargs.get("shell"))

    @patch("tests.run_tests.subprocess.run")
    def test_run_command_returns_exit_code(self, mock_run):
        """Test that run_command returns subprocess exit code."""
        mock_run.return_value = Mock(returncode=42)

        result = run_tests.run_command("some_command")

        self.assertEqual(result, 42)

    @patch("tests.run_tests.subprocess.run")
    def test_run_command_with_zero_exit_code(self, mock_run):
        """Test run_command with successful command (exit code 0)."""
        mock_run.return_value = Mock(returncode=0)

        result = run_tests.run_command("successful_command")

        self.assertEqual(result, 0)

    @patch("tests.run_tests.subprocess.run")
    def test_run_command_with_nonzero_exit_code(self, mock_run):
        """Test run_command with failed command (exit code != 0)."""
        mock_run.return_value = Mock(returncode=1)

        result = run_tests.run_command("failing_command")

        self.assertEqual(result, 1)


class TestRunAllFunction(unittest.TestCase):
    """Tests for the run_all function."""

    def test_run_all_exists(self):
        """Test that run_all function exists."""
        self.assertTrue(hasattr(run_tests, "run_all"))
        self.assertTrue(callable(run_tests.run_all))

    def test_run_all_has_docstring(self):
        """Test that run_all has descriptive docstring."""
        self.assertIsNotNone(run_tests.run_all.__doc__)
        self.assertIn("all tests", run_tests.run_all.__doc__.lower())

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_all_calls_run_command(self, mock_exit, mock_run_command):
        """Test that run_all calls run_command."""
        mock_run_command.return_value = 0

        run_tests.run_all()

        mock_run_command.assert_called_once()

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_all_tests_all_test_types(self, mock_exit, mock_run_command):
        """Test that run_all includes unit, component, and dependency tests."""
        mock_run_command.return_value = 0

        run_tests.run_all()

        command = mock_run_command.call_args[0][0]
        self.assertIn("tests.unit", command)
        self.assertIn("tests.component", command)
        self.assertIn("tests.dependency", command)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_all_exits_with_correct_code(self, mock_exit, mock_run_command):
        """Test that run_all exits with command exit code."""
        mock_run_command.return_value = 5

        run_tests.run_all()

        mock_exit.assert_called_once_with(5)


class TestRunUnitFunction(unittest.TestCase):
    """Tests for the run_unit function."""

    def test_run_unit_exists(self):
        """Test that run_unit function exists."""
        self.assertTrue(hasattr(run_tests, "run_unit"))
        self.assertTrue(callable(run_tests.run_unit))

    def test_run_unit_has_docstring(self):
        """Test that run_unit has descriptive docstring."""
        self.assertIsNotNone(run_tests.run_unit.__doc__)
        self.assertIn("unit test", run_tests.run_unit.__doc__.lower())

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_unit_calls_run_command(self, mock_exit, mock_run_command):
        """Test that run_unit calls run_command."""
        mock_run_command.return_value = 0

        run_tests.run_unit()

        mock_run_command.assert_called_once()

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_unit_tests_only_unit_tests(self, mock_exit, mock_run_command):
        """Test that run_unit only runs unit tests."""
        mock_run_command.return_value = 0

        run_tests.run_unit()

        command = mock_run_command.call_args[0][0]
        self.assertIn("tests.unit", command)
        self.assertNotIn("tests.component", command)
        self.assertNotIn("tests.dependency", command)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_unit_exits_with_correct_code(self, mock_exit, mock_run_command):
        """Test that run_unit exits with command exit code."""
        mock_run_command.return_value = 3

        run_tests.run_unit()

        mock_exit.assert_called_once_with(3)


class TestRunComponentFunction(unittest.TestCase):
    """Tests for the run_component function."""

    def test_run_component_exists(self):
        """Test that run_component function exists."""
        self.assertTrue(hasattr(run_tests, "run_component"))
        self.assertTrue(callable(run_tests.run_component))

    def test_run_component_has_docstring(self):
        """Test that run_component has descriptive docstring."""
        self.assertIsNotNone(run_tests.run_component.__doc__)
        self.assertIn("component test", run_tests.run_component.__doc__.lower())

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_component_calls_run_command(self, mock_exit, mock_run_command):
        """Test that run_component calls run_command."""
        mock_run_command.return_value = 0

        run_tests.run_component()

        mock_run_command.assert_called_once()

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_component_tests_only_component_tests(
        self, mock_exit, mock_run_command
    ):
        """Test that run_component only runs component tests."""
        mock_run_command.return_value = 0

        run_tests.run_component()

        command = mock_run_command.call_args[0][0]
        self.assertIn("tests.component", command)
        self.assertNotIn("tests.unit", command)
        self.assertNotIn("tests.dependency", command)


class TestRunDependencyFunction(unittest.TestCase):
    """Tests for the run_dependency function."""

    def test_run_dependency_exists(self):
        """Test that run_dependency function exists."""
        self.assertTrue(hasattr(run_tests, "run_dependency"))
        self.assertTrue(callable(run_tests.run_dependency))

    def test_run_dependency_has_docstring(self):
        """Test that run_dependency has descriptive docstring."""
        self.assertIsNotNone(run_tests.run_dependency.__doc__)
        self.assertIn("dependency test", run_tests.run_dependency.__doc__.lower())

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_dependency_calls_run_command(self, mock_exit, mock_run_command):
        """Test that run_dependency calls run_command."""
        mock_run_command.return_value = 0

        run_tests.run_dependency()

        mock_run_command.assert_called_once()

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_dependency_tests_only_dependency_tests(
        self, mock_exit, mock_run_command
    ):
        """Test that run_dependency only runs dependency tests."""
        mock_run_command.return_value = 0

        run_tests.run_dependency()

        command = mock_run_command.call_args[0][0]
        self.assertIn("tests.dependency", command)
        self.assertNotIn("tests.unit", command)
        self.assertNotIn("tests.component", command)


class TestRunPerformanceFunction(unittest.TestCase):
    """Tests for the run_performance function."""

    def test_run_performance_exists(self):
        """Test that run_performance function exists."""
        self.assertTrue(hasattr(run_tests, "run_performance"))
        self.assertTrue(callable(run_tests.run_performance))

    def test_run_performance_has_docstring(self):
        """Test that run_performance has descriptive docstring."""
        self.assertIsNotNone(run_tests.run_performance.__doc__)
        self.assertIn("performance", run_tests.run_performance.__doc__.lower())

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_performance_calls_run_command(self, mock_exit, mock_run_command):
        """Test that run_performance calls run_command."""
        mock_run_command.return_value = 0

        run_tests.run_performance()

        mock_run_command.assert_called_once()

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_performance_uses_locust(self, mock_exit, mock_run_command):
        """Test that run_performance uses locust command."""
        mock_run_command.return_value = 0

        run_tests.run_performance()

        command = mock_run_command.call_args[0][0]
        self.assertIn("locust", command)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_performance_specifies_locustfile(self, mock_exit, mock_run_command):
        """Test that run_performance specifies locustfile."""
        mock_run_command.return_value = 0

        run_tests.run_performance()

        command = mock_run_command.call_args[0][0]
        self.assertIn("locustfile_notifications.py", command)


class TestRunCoverageFunction(unittest.TestCase):
    """Tests for the run_coverage function."""

    def test_run_coverage_exists(self):
        """Test that run_coverage function exists."""
        self.assertTrue(hasattr(run_tests, "run_coverage"))
        self.assertTrue(callable(run_tests.run_coverage))

    def test_run_coverage_has_docstring(self):
        """Test that run_coverage has descriptive docstring."""
        self.assertIsNotNone(run_tests.run_coverage.__doc__)
        self.assertIn("coverage", run_tests.run_coverage.__doc__.lower())

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_coverage_calls_run_command_multiple_times(
        self, mock_exit, mock_run_command
    ):
        """Test that run_coverage calls run_command multiple times."""
        mock_run_command.return_value = 0

        run_tests.run_coverage()

        # Should call for: erase, run, report, html
        self.assertGreaterEqual(mock_run_command.call_count, 4)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_coverage_erases_previous_coverage(self, mock_exit, mock_run_command):
        """Test that run_coverage erases previous coverage data."""
        mock_run_command.return_value = 0

        run_tests.run_coverage()

        # First call should be coverage erase
        first_call = mock_run_command.call_args_list[0][0][0]
        self.assertIn("coverage erase", first_call)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_coverage_runs_tests_with_coverage(self, mock_exit, mock_run_command):
        """Test that run_coverage runs tests with coverage."""
        mock_run_command.return_value = 0

        run_tests.run_coverage()

        # One of the calls should run coverage
        commands = [call[0][0] for call in mock_run_command.call_args_list]
        has_coverage_run = any("coverage run" in cmd for cmd in commands)
        self.assertTrue(has_coverage_run)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_coverage_generates_html_report(self, mock_exit, mock_run_command):
        """Test that run_coverage generates HTML report."""
        mock_run_command.return_value = 0

        run_tests.run_coverage()

        # One of the calls should be coverage html
        commands = [call[0][0] for call in mock_run_command.call_args_list]
        has_html = any("coverage html" in cmd for cmd in commands)
        self.assertTrue(has_html)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_coverage_exits_on_failure(self, mock_exit, mock_run_command):
        """Test that run_coverage exits if any command fails."""
        # Make the second command fail (coverage run)
        mock_run_command.side_effect = [0, 1, 0, 0]

        run_tests.run_coverage()

        # Should call exit with error code (may be called multiple times in test)
        # Check that it was called with exit code 1
        exit_calls = [call[0][0] for call in mock_exit.call_args_list]
        self.assertIn(1, exit_calls)

    @patch("tests.run_tests.run_command")
    @patch("tests.run_tests.sys.exit")
    def test_run_coverage_exits_zero_on_success(self, mock_exit, mock_run_command):
        """Test that run_coverage exits with 0 on success."""
        mock_run_command.return_value = 0

        run_tests.run_coverage()

        mock_exit.assert_called_with(0)


class TestRunTestsModuleStructure(unittest.TestCase):
    """Tests for run_tests module structure."""

    def test_run_tests_module_exists(self):
        """Test that run_tests module can be imported."""
        self.assertIsNotNone(run_tests)

    def test_run_tests_module_has_docstring(self):
        """Test that run_tests module has docstring."""
        self.assertIsNotNone(run_tests.__doc__)
        self.assertGreater(len(run_tests.__doc__), 0)

    def test_subprocess_is_imported(self):
        """Test that subprocess module is imported."""
        self.assertTrue(hasattr(run_tests, "subprocess"))

    def test_sys_is_imported(self):
        """Test that sys module is imported."""
        self.assertTrue(hasattr(run_tests, "sys"))


class TestAllTestRunnerFunctions(unittest.TestCase):
    """Tests for all test runner functions collectively."""

    def test_all_runner_functions_have_docstrings(self):
        """Test that all runner functions have docstrings."""
        functions = [
            run_tests.run_all,
            run_tests.run_unit,
            run_tests.run_component,
            run_tests.run_dependency,
            run_tests.run_performance,
            run_tests.run_coverage,
        ]

        for func in functions:
            with self.subTest(function=func.__name__):
                self.assertIsNotNone(func.__doc__)
                self.assertGreater(len(func.__doc__), 0)

    def test_all_runner_functions_are_callable(self):
        """Test that all runner functions are callable."""
        functions = [
            run_tests.run_all,
            run_tests.run_unit,
            run_tests.run_component,
            run_tests.run_dependency,
            run_tests.run_performance,
            run_tests.run_coverage,
        ]

        for func in functions:
            with self.subTest(function=func.__name__):
                self.assertTrue(callable(func))


if __name__ == "__main__":
    unittest.main()
