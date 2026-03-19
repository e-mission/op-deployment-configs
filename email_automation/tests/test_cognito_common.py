import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, sentinel


EMAIL_AUTOMATION_DIR = Path(__file__).resolve().parents[1]
if str(EMAIL_AUTOMATION_DIR) not in sys.path:
    sys.path.insert(0, str(EMAIL_AUTOMATION_DIR))

if "boto3" not in sys.modules:
    sys.modules["boto3"] = types.SimpleNamespace(client=None)

import cognito_common as cc


def build_mock_cognito_client(user_pool, update_field_names=None):
    if update_field_names is None:
        update_field_names = (
            "UserPoolId",
            "PoolName",
            "EmailConfiguration",
            "SmsConfiguration",
            "UserAttributeUpdateSettings",
            "MfaConfiguration",
        )

    mock_cognito_client = MagicMock()
    mock_cognito_client.describe_user_pool.return_value = {"UserPool": user_pool}
    input_shape = types.SimpleNamespace(
        members={field_name: object() for field_name in update_field_names}
    )
    operation_model = types.SimpleNamespace(input_shape=input_shape)
    service_model = types.SimpleNamespace(
        operation_model=MagicMock(return_value=operation_model)
    )
    mock_cognito_client.meta = types.SimpleNamespace(service_model=service_model)
    return mock_cognito_client


class TestCognitoCommon(unittest.TestCase):
    def test_derive_program_name_from_config(self):
        self.assertEqual(
            cc.derive_program_name_from_config("configs/open-access.nrel-op.json"),
            "open-access",
        )

    def test_derive_pool_name_from_config(self):
        self.assertEqual(
            cc.derive_pool_name_from_config("open-access"),
            "nrelopenpath-prod-open-access",
        )

    def test_derive_config_path_local(self):
        config_path = cc.derive_config_path(
            "configs/open-access-openpath.nrel-op.json",
            True,
            "/Users/test/openpath-deploy-configs/email_automation/email-config.py",
        )
        self.assertEqual(config_path, "configs/open-access-openpath.nrel-op.json")

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

    def test_update_user_pool(self):
        mock_cognito_client = build_mock_cognito_client(
            {
                "Id": "us-west-2_abc123",
                "Name": "test-pool",
                "EmailConfiguration": {
                    "SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/old@example.com"
                },
            }
        )

        cc.update_user_pool(
            "us-west-2_abc123",
            "EmailConfiguration",
            "EmailConfiguration",
            {"SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/new@example.com"},
            mock_cognito_client,
        )

        mock_cognito_client.update_user_pool.assert_called_once_with(
            UserPoolId="us-west-2_abc123",
            PoolName="test-pool",
            EmailConfiguration={
                "SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/new@example.com"
            },
        )

    def test_update_user_pool_different_key(self):
        mock_cognito_client = build_mock_cognito_client(
            {
                "Id": "us-west-2_def456",
                "Name": "test-pool-2",
                "SmsConfiguration": {
                    "ExternalId": "old-external-id",
                    "SnsCallerArn": "arn:aws:iam::123456789012:role/old-role",
                },
            }
        )

        cc.update_user_pool(
            "us-west-2_def456",
            "SmsConfiguration",
            "SmsConfiguration",
            {"ExternalId": "new-external-id"},
            mock_cognito_client,
        )

        mock_cognito_client.update_user_pool.assert_called_once_with(
            UserPoolId="us-west-2_def456",
            PoolName="test-pool-2",
            SmsConfiguration={
                "ExternalId": "new-external-id",
                "SnsCallerArn": "arn:aws:iam::123456789012:role/old-role",
            },
        )

    def test_update_user_pool_keep_original(self):
        mock_cognito_client = build_mock_cognito_client(
            {
                "Id": "us-west-2_xyz789",
                "Name": "test-pool-3",
                "UserAttributeUpdateSettings": {
                    "AttributesRequireVerificationBeforeUpdate": ["email", "phone_number"]
                },
            }
        )

        cc.update_user_pool(
            "us-west-2_xyz789",
            "EmailConfiguration",
            "EmailConfiguration",
            {"SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/new@example.com"},
            mock_cognito_client,
        )

        mock_cognito_client.update_user_pool.assert_called_once_with(
            UserPoolId="us-west-2_xyz789",
            PoolName="test-pool-3",
            UserAttributeUpdateSettings={
                "AttributesRequireVerificationBeforeUpdate": ["email", "phone_number"]
            },
            EmailConfiguration={
                "SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/new@example.com"
            },
        )

    def test_update_user_pool_does_not_call_mfa_factor_api(self):
        mock_cognito_client = build_mock_cognito_client(
            {
                "Id": "us-west-2_mfa123",
                "Name": "mfa-pool",
                "MfaConfiguration": "OPTIONAL",
            }
        )

        cc.update_user_pool(
            "us-west-2_mfa123",
            "EmailConfiguration",
            "EmailConfiguration",
            {"SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/new@example.com"},
            mock_cognito_client,
        )

        mock_cognito_client.update_user_pool.assert_called_once_with(
            UserPoolId="us-west-2_mfa123",
            PoolName="mfa-pool",
            MfaConfiguration="OPTIONAL",
            EmailConfiguration={
                "SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/new@example.com"
            },
        )
        mock_cognito_client.get_user_pool_mfa_config.assert_not_called()
        mock_cognito_client.set_user_pool_mfa_config.assert_not_called()

    def test_update_user_pool_skips_non_model_fields(self):
        mock_cognito_client = build_mock_cognito_client(
            {
                "Id": "us-west-2_model123",
                "Name": "model-pool",
                "SchemaAttributes": [{"Name": "email"}],
                "UsernameAttributes": ["email"],
                "EstimatedNumberOfUsers": 7,
                "Arn": "arn:aws:cognito-idp:us-west-2:123456789012:userpool/us-west-2_model123",
                "EmailConfiguration": {
                    "SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/old@example.com"
                },
            }
        )

        cc.update_user_pool(
            "us-west-2_model123",
            "EmailConfiguration",
            "EmailConfiguration",
            {"From": "OpenPATH <new@example.com>"},
            mock_cognito_client,
        )

        mock_cognito_client.update_user_pool.assert_called_once_with(
            UserPoolId="us-west-2_model123",
            PoolName="model-pool",
            EmailConfiguration={
                "SourceArn": "arn:aws:ses:us-west-2:123456789012:identity/old@example.com",
                "From": "OpenPATH <new@example.com>",
            },
        )

    @patch("builtins.input", return_value="alice LIST IS FINE")
    @patch("builtins.print")
    def test_validate_check_done_success(self, mock_print, _mock_input):
        username = cc.validate_check_done()

        self.assertEqual(username, "alice")
        mock_print.assert_any_call("Running script as user alice")

    @patch("builtins.input", return_value="bad confirmation text")
    @patch("builtins.print")
    def test_validate_check_done_failure(self, mock_print, _mock_input):
        username = cc.validate_check_done()

        self.assertIsNone(username)
        mock_print.assert_any_call("Error: expected format '<username> LIST IS FINE'")

    @patch("builtins.input", return_value="alice LIST IS FINE and I didn't check")
    @patch("builtins.print")
    def test_validate_check_done_extra_text(self, mock_print, _mock_input):
        username = cc.validate_check_done()

        self.assertIsNone(username)
        mock_print.assert_any_call("Error: expected format '<username> LIST IS FINE'")

if __name__ == "__main__":
    unittest.main()