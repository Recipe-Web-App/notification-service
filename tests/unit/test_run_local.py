"""Unit tests for run_local module."""

import unittest
from unittest.mock import patch

import run_local


class TestRunLocal(unittest.TestCase):
    """Tests for run_local script."""

    @patch("run_local.execute_from_command_line")
    def test_main_calls_runlocal(self, mock_execute):
        """Test that main() calls Django's runlocal command."""
        run_local.main()

        mock_execute.assert_called_once()
        args = mock_execute.call_args[0][0]
        self.assertIn("runlocal", args)

    def test_script_has_main_function(self):
        """Test that script has a main() function."""
        self.assertTrue(hasattr(run_local, "main"))
        self.assertTrue(callable(run_local.main))

    def test_module_has_correct_docstring(self):
        """Test that module has expected docstring."""
        self.assertIsNotNone(run_local.__doc__)
        self.assertIn("Django development server", run_local.__doc__)


if __name__ == "__main__":
    unittest.main()
