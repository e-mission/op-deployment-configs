import os

import boto3


def derive_program_name_from_config(config_path):
    return os.path.basename(config_path).split(".")[0]


def derive_config_path(config_path_arg, local, script_file):
    if local:
        return config_path_arg
    repo_root = os.path.dirname(os.path.dirname(script_file))
    return os.path.join(repo_root, "configs", os.path.basename(config_path_arg))


def derive_pool_name_from_config(program_name):
    return "nrelopenpath-prod-" + program_name


def get_region(local):
    return "us-west-2" if local else os.environ.get("AWS_REGION")


def build_cognito_client(local):
    aws_region = "us-west-2" if local else os.environ.get("AWS_REGION")
    if local:
        return boto3.client(
            "cognito-idp",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
            region_name=aws_region,
        )
    return boto3.client("cognito-idp", region_name=aws_region)


def build_sts_client(local):
    aws_region = "us-west-2" if local else os.environ.get("AWS_REGION")
    if local:
        return boto3.client(
            "sts",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
            region_name=aws_region,
        )
    return None


def read_userpool_obj_list_on_all_pages(cognito_client, verbose=False):
    # From https://stackoverflow.com/a/64698263
    response = cognito_client.list_user_pools(MaxResults=60)
    next_token = response.get("NextToken", None)
    if verbose:
        print(f'Received response with {len(response["UserPools"])=} and {next_token=}')
    user_pool_obj_list = response["UserPools"]
    while next_token is not None:
        response = cognito_client.list_user_pools(NextToken=next_token, MaxResults=60)
        next_token = response.get("NextToken", None)
        if verbose:
            print(f'Received response with {len(response["UserPools"])=} & {next_token=}')
        user_pool_obj_list.extend(response["UserPools"])
    return user_pool_obj_list


def get_userpool_id(pool_name, cognito_client, verbose=False):
    if verbose:
        print(f"Called get_userpool_id with {pool_name=} and {verbose}")
    all_user_pools = read_userpool_obj_list_on_all_pages(cognito_client, verbose=verbose)
    pool_names = [user_pool["Name"] for user_pool in all_user_pools]
    if verbose:
        print(f"Pool names: {pool_names}")
    if pool_name not in pool_names:
        return False, None
    pool_index = pool_names.index(pool_name)
    if verbose:
        print(f"Found {pool_name=} at {pool_index=} with id {all_user_pools[pool_index]['Id']}")
    return True, all_user_pools[pool_index]["Id"]


def get_all_users(pool_id, cognito_client):
    response = cognito_client.list_users(UserPoolId=pool_id)
    users = response["Users"]
    # note that this is not strictly required in our case since we only support
    # < 5 admin users. But it is good to refactor so we can bake in that assumption
    # in a common function and improve it if necessary
    pagination_token = response.get("PaginationToken", None)
    while pagination_token is not None:
        response = cognito_client.list_users(
            UserPoolId=pool_id,
            PaginationToken=pagination_token,
        )
        users.extend(response["Users"])
        pagination_token = response.get("PaginationToken", None)
    return users