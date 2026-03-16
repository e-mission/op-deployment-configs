import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch, sentinel


EMAIL_AUTOMATION_DIR = Path(__file__).resolve().parents[1]
if str(EMAIL_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(EMAIL_AUTOMATION_DIR))

if "boto3" not in sys.modules:
    sys.modules["boto3"] = types.SimpleNamespace(client=None)

import cognito_common as cc


class TestCognitoCommon(unittest.TestCase):
    def test_derive_program_name_from_config(self):
        self.assertEqual(
            cc.derive_program_name_from_config("configs/open-access-openpath.nrel-op.json"),
            "open-access-openpath",
        )

    def test_derive_pool_name_from_config(self):
        self.assertEqual(
            cc.derive_pool_name_from_config("open-access-openpath"),
            "nrelopenpath-prod-open-access-openpath",
        )

    def test_derive_config_path_local(self):
        config_path = cc.derive_config_path(
            "configs/open-access-openpath.nrel-op.json",
            True,
            "/Users/test/openpath-deploy-configs/email_automation/email-config.py",
        )
        self.assertEqual(config_path, "configs/open-access.nrel-op.json")

    def test_derive_config_path_github(self):
        config_path = cc.derive_config_path(
            "configs/open-access.nrel-op.json",
            False,
            "/Users/test/openpath-deploy-configs/email_automation/email-config.py",
        )
        self.assertEqual(
            config_path,
            "/Users/test/openpath-deploy-configs/configs/open-access.nrel-op.json",
        )

    @patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=False)
    def test_get_region(self):
        self.assertEqual(cc.get_region(True), "us-west-2")
        self.assertEqual(cc.get_region(False), "us-east-1")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "access",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "token",
        },
        clear=False,
    )
    @patch("cognito_common.boto3.client")
    def test_build_cognito_client_local(self, mock_client):
        mock_client.return_value = sentinel.cognito_client

        client = cc.build_cognito_client(True)

        self.assertIs(client, sentinel.cognito_client)
        mock_client.assert_called_once_with(
            "cognito-idp",
            aws_access_key_id="access",
            aws_secret_access_key="secret",
            aws_session_token="token",
            region_name="us-west-2",
        )

    @patch.dict(os.environ, {"AWS_REGION": "us-east-1"}, clear=False)
    @patch("cognito_common.boto3.client")
    def test_build_cognito_client_github(self, mock_client):
        mock_client.return_value = sentinel.cognito_client

        client = cc.build_cognito_client(False)

        self.assertIs(client, sentinel.cognito_client)
        mock_client.assert_called_once_with("cognito-idp", region_name="us-east-1")

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "access",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_SESSION_TOKEN": "token",
        },
        clear=False,
    )
    @patch("cognito_common.boto3.client")
    def test_build_sts_client_local(self, mock_client):
        mock_client.return_value = sentinel.sts_client

        client = cc.build_sts_client(True)

        self.assertIs(client, sentinel.sts_client)
        mock_client.assert_called_once_with(
            "sts",
            aws_access_key_id="access",
            aws_secret_access_key="secret",
            aws_session_token="token",
            region_name="us-west-2",
        )

    @patch("cognito_common.boto3.client")
    def test_build_sts_client_github(self, mock_client):
        client = cc.build_sts_client(False)

        self.assertIsNone(client)
        mock_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()