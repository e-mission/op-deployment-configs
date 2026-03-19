import importlib.util
import sys
import types
import unittest
from pathlib import Path


EMAIL_AUTOMATION_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = EMAIL_AUTOMATION_DIR / "update-email-sender.py"

if str(EMAIL_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(EMAIL_AUTOMATION_DIR))

if "botocore" not in sys.modules:
    botocore_exceptions = types.SimpleNamespace(ClientError=Exception)
    sys.modules["botocore"] = types.SimpleNamespace(exceptions=botocore_exceptions)
    sys.modules["botocore.exceptions"] = botocore_exceptions

if "cognito_common" not in sys.modules:
    sys.modules["cognito_common"] = types.SimpleNamespace()


spec = importlib.util.spec_from_file_location("update_email_sender", SCRIPT_PATH)
update_email_sender = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_email_sender)


class TestUpdateEmailSender(unittest.TestCase):
    def test_get_identity_email_plain_email(self):
        self.assertEqual(
            update_email_sender.get_identity_email("openpath@nrel.gov"),
            "openpath@nrel.gov",
        )

    def test_get_identity_email_display_name(self):
        self.assertEqual(
            update_email_sender.get_identity_email("OpenPATH <openpath@nrel.gov>"),
            "openpath@nrel.gov",
        )

    def test_get_identity_email_invalid_value(self):
        with self.assertRaisesRegex(ValueError, "Could not parse email identity"):
            update_email_sender.get_identity_email("OpenPATH")


if __name__ == "__main__":
    unittest.main()