import argparse
import logging
import email.utils as eu

import botocore.exceptions as be

import cognito_common as cc


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def get_identity_email(address):
    _display_name, identity_email = eu.parseaddr(address)
    if not identity_email or "@" not in identity_email:
        raise ValueError(f"Could not parse email identity from {address!r}")
    return identity_email


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

    cc.update_user_pool(
        pool_id,
        "EmailConfiguration",
        "EmailConfiguration",
        desired_email_configuration,
        cognito_client,
    )
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update Cognito user pools to change the sender that the authentication emails are sent from."
    )
    group_action = parser.add_mutually_exclusive_group(required=True)
    group_action.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List matching pools only; make no changes.",
    )
    group_action.add_argument(
        "-s",
        "--set",
        action="store_true",
        help="Apply updates to matching pools.",
    )
    parser.add_argument(
        "--old-address",
        default="openpath@nrel.gov",
        help="Current From address, optionally with display name, e.g. 'OpenPATH <openpath@nrel.gov>'.",
    )
    parser.add_argument(
        "--new-address",
        default="openpath@nlr.gov",
        help="New From address, optionally with display name, e.g. 'OpenPATH <openpath@nlr.gov>'.",
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
    group_selection = parser.add_mutually_exclusive_group()
    group_selection.add_argument(
        "-p",
        "--pool",
        default="nrelopenpath-prod-",
        help="Pool name or prefix to match (default: 'nrelopenpath-prod-').",
    )
    group_selection.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Match all pools (overrides --pool).",
    )
    args = parser.parse_args()

    cognito_client = cc.build_cognito_client(True)

    user_pools = cc.read_userpool_obj_list_on_all_pages(cognito_client, verbose=args.verbose)
    
    if args.all:
        matching_pools = user_pools
        pool_filter_desc = "all pools"
    else:
        matching_pools = [
            user_pool for user_pool in user_pools if user_pool["Name"].startswith(args.pool)
        ]
        pool_filter_desc = f"prefix '{args.pool}'"

    if not matching_pools:
        print(f"No user pools found matching {pool_filter_desc}")
        raise SystemExit(0)
    if args.list:
        print(f"Found {len(matching_pools)} user pool(s) matching {pool_filter_desc}:")
        for pool_obj in matching_pools:
            print(f"----- {pool_obj['Name']} ({pool_obj['Id']}) -----")
            print(f"{cognito_client.describe_user_pool(UserPoolId=pool_obj['Id'])['UserPool']}")
        raise SystemExit(0)

    if not cc.validate_check_done():
        raise SystemExit(0)

    sts_client = cc.build_sts_client(True)
    aws_region = cc.get_region(True)

    sts_account_num = sts_client.get_caller_identity()["Account"]
    old_identity_email = get_identity_email(args.old_address)
    new_identity_email = get_identity_email(args.new_address)
    old_source_arn = f"arn:aws:ses:{aws_region}:{sts_account_num}:identity/{old_identity_email}"
    new_source_arn = f"arn:aws:ses:{aws_region}:{sts_account_num}:identity/{new_identity_email}"
    expected_current_configuration = {
        "SourceArn": old_source_arn,
        "EmailSendingAccount": "DEVELOPER",
        "From": args.old_address,
    }

    desired_email_configuration = {
        "SourceArn": new_source_arn,
        "EmailSendingAccount": "DEVELOPER",
        "From": args.new_address,
    }

    print(f"Found {len(matching_pools)} user pool(s) matching {pool_filter_desc}, updating them...")

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