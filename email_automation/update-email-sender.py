import argparse
import logging

import botocore.exceptions as be

import cognito_common as cc


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def update_pool_email_configuration(pool_obj, cognito_client, expected_current_configuration, desired_email_configuration, dry_run):
    pool_name = pool_obj["Name"]
    pool_id = pool_obj["Id"]
    pool_description = cognito_client.describe_user_pool(UserPoolId=pool_id)["UserPool"]
    current_email_configuration = pool_description.get("EmailConfiguration") or {}

    if all(current_email_configuration.get(key) == value for key, value in desired_email_configuration.items()):
        print(f"{pool_name}: already configured")
        return False

    if not all(current_email_configuration.get(key) == value for key, value in expected_current_configuration.items()):
        print(
             f"WARNING: {pool_name} ({pool_id}) misconfigured; "
             f"Found {current_email_configuration=}, {expected_current_configuration=}. Skipping."
        )
        return False

    print(f"{pool_name}: updating email sender")
    print(f"  current from: {current_email_configuration.get('From')}")
    print(f"  target from:  {desired_email_configuration['From']}")

    if dry_run:
        print("  dry run only; no changes applied")
        return False

    update_request = cc.build_user_pool_update_request(
        pool_description,
        "EmailConfiguration",
        "EmailConfiguration",
        desired_email_configuration,
    )
    cognito_client.update_user_pool(**update_request)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Cognito user pools to change the sender that the authentication emails are sent from."
    )
    parser.add_argument(
        "--old-address",
        default="openpath@nrel.gov",
        help="Verified SES address currently configured as the sender (used for safety check).",
    )
    parser.add_argument(
        "--new-address",
        default="openpath@nlr.gov",
        help="Verified SES address to configure as the new sender.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the pools that would be updated without applying changes.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print pagination progress while listing user pools.",
    )
    args = parser.parse_args()

    if not cc.validate_check_done():
        raise SystemExit(0)

    cognito_client = cc.build_cognito_client(True)
    sts_client = cc.build_sts_client(True)
    aws_region = cc.get_region(True)

    sts_account_num = sts_client.get_caller_identity()["Account"]
    old_source_arn = f"arn:aws:ses:{aws_region}:{sts_account_num}:identity/{args.old_address}"
    new_source_arn = f"arn:aws:ses:{aws_region}:{sts_account_num}:identity/{args.new_address}"
    expected_current_configuration = {
        "SourceArn": old_source_arn,
        "From": args.old_address,
    }
    
    desired_email_configuration = {
        "SourceArn": new_source_arn,
        "EmailSendingAccount": "DEVELOPER",
        "From": args.new_address,
    }

    user_pools = cc.read_userpool_obj_list_on_all_pages(cognito_client, verbose=args.verbose)
    matching_pools = [
        user_pool for user_pool in user_pools if user_pool["Name"].startswith("nrelopenpath-prod-")
    ]

    if not matching_pools:
        print(f"No user pools found matching prefix 'nrelopenpath-prod-'")
        raise SystemExit(0)
    else:
        print(f"Found {len(matching_pools)} user pool(s) matching prefix 'nrelopenpath-prod-', updating them...")

    updated_count = 0
    for pool_obj in matching_pools:
        try:
            updated = update_pool_email_configuration(
                pool_obj,
                cognito_client,
                expected_current_configuration,
                desired_email_configuration,
                args.dry_run,
            )
            updated_count += int(updated)
        except be.ClientError as err:
            logger.error(
                "Failed to update %s. Here's why: %s: %s",
                pool_obj["Name"],
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

    print(f"Processed {len(matching_pools)} pool(s); updated {updated_count}.")