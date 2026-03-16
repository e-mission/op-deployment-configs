import botocore.exceptions as be
import logging
import sys
import argparse

import cognito_common as cc

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# If you don't have boto3 installed, make sure to `pip install boto3` before running this script.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Read and display Cognito user profiles from a specified user pool."
    )

    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument(
        '-l', '--local',
        action='store_true',
        help='Running locally. Reads AWS credentials from environment variables.'
    )
    auth_group.add_argument(
        '-g', '--github',
        action='store_true',
        help='Must be run on GitHub Actions.'
    )

    pool_group = parser.add_mutually_exclusive_group(required=True)
    pool_group.add_argument(
        '-p', '--pool-name',
        help='Full Cognito user pool name (e.g. nrelopenpath-prod-myprogram)'
    )
    pool_group.add_argument(
        '-c', '--config',
        help='Path to a config file; pool name will be derived as nrelopenpath-prod-<filename>'
    )

    args = parser.parse_args()

    if args.config:
        program_name = cc.derive_program_name_from_config(args.config)
        pool_name = cc.derive_pool_name_from_config(program_name)
    else:
        pool_name = args.pool_name

cognito_client = cc.build_cognito_client(args.local)


def display_user(user):
    for key in sorted(user.keys()):
        print(f"  {key}: {user[key]}")
    print()


######################################################################
is_userpool_exist, pool_id = cc.get_userpool_id(pool_name, cognito_client, verbose=True)

if not is_userpool_exist:
    print(f"{pool_name} does not exist. Check the pool name and try again.")
    sys.exit(1)

try:
    users = cc.get_all_users(pool_id, cognito_client)
except be.ClientError as err:
    logger.error(
        "Couldn't list users for %s. Here's why: %s: %s",
        pool_id,
        err.response["Error"]["Code"],
        err.response["Error"]["Message"],
    )
    raise
print(f"\nUser pool: {pool_name}  ({pool_id})")
print(f"Total users: {len(users)}\n")
print("-" * 60)

for user in users:
    display_user(user)
