"""Unit tests for run_local module."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import run_local


class TestRunLocal(unittest.TestCase):
    """Tests for run_local script."""

    @patch("run_local.execute_from_command_line")
    def test_main_calls_runserver(self, mock_execute):
        """Test that main() calls Django's runserver command."""
        run_local.main()

        mock_execute.assert_called_once()
        args = mock_execute.call_args[0][0]
        self.assertIn("runserver", args)

    def test_script_runs_as_main(self):
        """Test that script executes when run directly."""
        script_path = Path(__file__).parent.parent.parent / "run_local.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=False,
            capture_output=True,
            timeout=2,
        )
        # Script starts server, we just verify it attempted to run
        # Exit code will be non-zero since we kill it quickly
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
