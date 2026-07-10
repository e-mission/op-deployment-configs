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


if __name__ == "__main__":
    unittest.main()