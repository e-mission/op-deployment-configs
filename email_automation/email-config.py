import boto3
from botocore.exceptions import ClientError
import json
import os
import logging
import sys
import argparse
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# If you don't have boto3 installed, make sure to `pip install boto3` before running this script. 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-l', '--local',
                       help = 'Running locally. Provide full path to config file + install boto3 prior to running.' )
    group.add_argument('-g', '--github',
                       help = 'Must be run on GitHub. To run locally, use -l argument.') 
    args = parser.parse_args()
    filepath_raw = sys.argv[2]
    filename_raw = filepath_raw.split("/")[-1]
    filename = filename_raw.split('.')[0]
    pool_name = "nrelopenpath-prod-" + filename
    current_path = os.path.dirname(__file__)
    maindir = current_path.rsplit("/",1)[0]
    config_path = filepath_raw if args.local else maindir + f'/configs/{filename_raw}'

if args.local:
    #Set up AWS credentials as environment variables + set variables 
    ACCESS = os.environ.get("AWS_ACCESS_KEY_ID")
    SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY")
    TOKEN = os.environ.get("AWS_SESSION_TOKEN")
    AWS_REGION = "us-west-2"

    #Set up clients
    cognito_client = boto3.client(
        'cognito-idp',
        aws_access_key_id = ACCESS,
        aws_secret_access_key= SECRET,
        aws_session_token=TOKEN, 
        region_name=AWS_REGION
        )

    sts_client = boto3.client(
        'sts',
        aws_access_key_id = ACCESS,
        aws_secret_access_key= SECRET,
        aws_session_token=TOKEN, 
        region_name=AWS_REGION
        )
if args.github:
    AWS_REGION = os.environ.get("AWS_REGION")
    cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)
    sts_client = ''

def read_userpool_obj_list_on_all_pages(cognito_client):
    # From https://stackoverflow.com/a/64698263
    response = cognito_client.list_user_pools(MaxResults=60)
    next_token = response.get("NextToken", None)
    print(f'Received response with {len(response["UserPools"])=} and {next_token=}')
    user_pool_obj_list = response["UserPools"]
    while next_token is not None:
        response = cognito_client.list_user_pools(NextToken=next_token, MaxResults=60)
        next_token = response.get("NextToken", None)
        print(f'Received response with {len(response["UserPools"])=} & {next_token=}')
        user_pool_obj_list.extend(response["UserPools"])
    return user_pool_obj_list

# Functions 
def get_userpool_name(pool_name, cognito_client):
    all_user_pools = read_userpool_obj_list_on_all_pages(cognito_client)
    is_userpool_exist = False
    user_pools = [user_pool["Name"] for user_pool in all_user_pools]
    is_userpool_exist = True if pool_name in user_pools else False
    user_pool_index = user_pools.index(pool_name) if is_userpool_exist else None
    pool_id = all_user_pools[user_pool_index]["Id"] if is_userpool_exist else None
    return is_userpool_exist, pool_id

def get_users(pool_id, cognito_client):
    try:
        response = cognito_client.list_users(UserPoolId=pool_id)
        return response["Users"]
    except ClientError as err:
        logger.error(
            "Couldn't list users for %s. Here's why: %s: %s",
            pool_id,
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        raise

def get_verified_arn(sts_client):
    if args.local:
        account_num = sts_client.get_caller_identity()["Account"]
        identity_arn = "arn:aws:ses:" + AWS_REGION + ":" + account_num + ":identity/openpath@nrel.gov"
    if args.github:
        AWS_ACCT_ID = os.environ.get("AWS_ACCT_ID")
        identity_arn = "arn:aws:ses:" + AWS_REGION + ":" + AWS_ACCT_ID + ":identity/openpath@nrel.gov"
    return identity_arn

def email_extract():
    with open (config_path) as config_file:
        data = json.load(config_file)
        admindash_prefs = data['admin_dashboard']
        emails = [i.strip().lstrip() for i in admindash_prefs.get('admin_access', [])]
        columns_exclude = admindash_prefs['data_trips_columns_exclude']
        map_trip_lines_enabled = admindash_prefs['map_trip_lines']
    return emails, map_trip_lines_enabled, columns_exclude

def create_account(pool_id, email, cognito_client):
    response = cognito_client.admin_create_user(
                    UserPoolId = pool_id,
                    Username=email,
                    UserAttributes=[
                        {
                            'Name': 'email',
                            'Value': email,
                        },
                    ],
                    ForceAliasCreation=True,
                    DesiredDeliveryMediums=[
                        'EMAIL',
                    ],
                )
    return response

def format_email(filename, map_trip_lines_enabled, columns_exclude):
    with open(maindir + '/email_automation/welcome-template.txt', 'r') as f:
        html = f.read()
        html = html.replace('<filename>', filename)
        if map_trip_lines_enabled:
            html = html.replace ('<map_trip_lines>', 'Additionally, you can view individual user-origin destination points using the "Map Lines" option from the map page.')
        else:
            html = html.replace ('<map_trip_lines>', '')
        if 'data.start_loc.coordinates' in columns_exclude or 'data.end_loc.coordinates' in columns_exclude:
            html = html.replace ('<columns_exclude>', 'Per your requested configuration, your trip table excludes trip start/end coordinates for greater anonymity. Let us know if you need them to be enabled for improved analysis.')
        elif columns_exclude == '':
            html = html.replace ('<columns_exclude>', 'Since you indicated that you want to map the data to infrastructure updates, your configuration includes trip start/end in the trip table. Let us know if you would like to exclude those for greater anonymity.')
        return html
        

def update_user_pool(pool_id, pool_name, html, identity_arn, cognito_client):
  response = cognito_client.update_user_pool(
        UserPoolId= pool_id,
        AutoVerifiedAttributes=['email'],
        EmailConfiguration={
            'SourceArn': identity_arn,
            'EmailSendingAccount': 'DEVELOPER',
            'From': 'openpath@nrel.gov'
        },
        AdminCreateUserConfig={
            'AllowAdminCreateUserOnly': True,
            'InviteMessageTemplate': {
                'EmailMessage': str(html),
                'EmailSubject': f'Welcome to {pool_name} user pool!'
            }
        },
)

def remove_user(pool_id, user):
    response = cognito_client.admin_delete_user(
        UserPoolId= pool_id,
        Username= str(user)
)
######################################################################
is_userpool_exist, pool_id = get_userpool_name(pool_name, cognito_client) 

 # Start by checking for the User Pool. If the User Pool does not yet exist, wait until it is set up to add users. 
if is_userpool_exist:
    #extract email addresses from config file
    emails, map_trip_lines_enabled, columns_exclude = email_extract()
    users = get_users(pool_id, cognito_client)
    for user in users:
        for attr_dict in user["Attributes"]:
            if attr_dict["Name"] == "email":
                user_email = attr_dict["Value"]
                if user_email not in emails:
                    remove_user(pool_id, user_email)
                    print(f"{user_email} removed from pool.")
        
    #Loop over each email address. Check if they're in the user pool.
    for email in emails:
        if not str(users).find(email) > 1:
            #If user not in pool, format the email template for their welcome email, update the user pool, and create an account for them.
            print(email + " not in user pool! Creating account...")
            html = format_email(filename, map_trip_lines_enabled, columns_exclude)
            identity_arn = get_verified_arn(sts_client)
            update_user_pool(pool_id, pool_name, html, identity_arn, cognito_client)
            response = create_account(pool_id, email, cognito_client)
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                print("Account created! Sending welcome email.")
            else:
                print("Account creation unsuccessful.")
                print(response['ResponseMetadata']['HTTPStatusCode'])       
        else:
            print(email + " already in user pool!")
else:
    print(pool_name + " does not exist! Try again later.")
