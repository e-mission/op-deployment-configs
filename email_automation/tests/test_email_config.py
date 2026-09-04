import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

EMAIL_AUTOMATION_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = EMAIL_AUTOMATION_DIR / "email-config.py"

if "botocore" not in sys.modules:
    botocore_exceptions = types.SimpleNamespace(ClientError=Exception)
    sys.modules["botocore"] = types.SimpleNamespace(exceptions=botocore_exceptions)
    sys.modules["botocore.exceptions"] = botocore_exceptions

if "cognito_common" not in sys.modules:
    sys.modules["cognito_common"] = types.SimpleNamespace()


def _load_email_config():
    spec = importlib.util.spec_from_file_location("email_config", SCRIPT_PATH)
    email_config = importlib.util.module_from_spec(spec)
    mock_cc = MagicMock()
    mock_cc.get_userpool_id.return_value = (False, None)
    email_config.__dict__.update({
        "cc": mock_cc,
        "args": types.SimpleNamespace(local=True, github=False, quiet=True),
        "pool_name": "test-pool",
        "config_path": "/dev/null",
        "maindir": str(EMAIL_AUTOMATION_DIR.parent),
        "program_name": "test-program",
    })
    spec.loader.exec_module(email_config)
    return email_config


_ec = _load_email_config()


class TestFormatEmail(unittest.TestCase):
    def _call(self, admin_dash_config=None):
        return _ec.format_email("my-program", admin_dash_config or {})

    def test_default_config(self):
        """No special config: map trip lines text absent, all columns included."""
        result = self._call()
        self.assertIn("<html>", result)
        self.assertNotIn("Map Lines", result)
        self.assertIn("all available columns", result)
        self.assertIn("adjust these settings", result)

    def test_map_trip_lines_enabled(self):
        result = self._call({"map_trip_lines": True})
        self.assertIn("Map Lines", result)

    def test_no_columns_excluded(self):
        """If no columns are excluded, the email should say all columns are included."""
        result = self._call()
        self.assertIn("all available columns", result)
        self.assertNotIn("will exclude the following", result)

    def test_columns_excluded(self):
        """All three exclusion lists produce the right sections and preamble."""
        config = {
            "data_uuids_columns_exclude": ["user_id"],
            "data_trips_columns_exclude": ["start_loc", "end_loc"],
            "data_trajectories_columns_exclude": ["coordinates"],
        }
        result = self._call(config)
        self.assertIn("will exclude the following", result)
        self.assertIn("Users: user_id", result)
        self.assertIn("Trips: start_loc, end_loc", result)
        self.assertIn("Trajectories: coordinates", result)
        self.assertNotIn("all available columns", result)

    def test_some_columns_excluded(self):
        """If only some exclusion lists are populated, only those sections should appear."""
        config = {
            "data_trips_columns_exclude": ["start_loc", "end_loc"],
        }
        result = self._call(config)
        self.assertIn("will exclude the following", result)
        self.assertIn("Trips: start_loc, end_loc", result)
        self.assertNotIn("Users:", result)
        self.assertNotIn("Trajectories:", result)
        self.assertNotIn("all available columns", result)

if __name__ == "__main__":
    unittest.main()
