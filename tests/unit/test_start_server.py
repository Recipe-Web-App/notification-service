"""Unit tests for start_server module."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import start_server


class TestStartServer(unittest.TestCase):
    """Tests for start_server script."""

    @patch("start_server.run")
    def test_main_configures_and_runs_gunicorn(self, mock_run):
        """Test that main() configures and starts Gunicorn."""
        start_server.main()

        mock_run.assert_called_once()

    def test_script_runs_as_main(self):
        """Test that script executes when run directly."""
        script_path = Path(__file__).parent.parent.parent / "start_server.py"

        # Script starts a server, so it will timeout - that's expected
        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run(
                [sys.executable, str(script_path)],
                check=False,
                capture_output=True,
                timeout=1,
            )


if __name__ == "__main__":
    unittest.main()
