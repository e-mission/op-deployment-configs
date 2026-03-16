import botocore.exceptions as be
import json
import os
import logging
import argparse

import cognito_common as cc
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# If you don't have boto3 installed, make sure to `pip install boto3` before running this script. 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument('-l', '--local',
                       action='store_true',
                       help = 'Running locally. Reads AWS credentials from environment variables.' )
    auth_group.add_argument('-g', '--github',
                       action='store_true',
                       help = 'Must be run on GitHub. To run locally, use -l argument.') 
    
    parser.add_argument('-p', '--pool-name',
                       help = 'Cognito user pool name (e.g. nrelopenpath-prod-myprogram). If not provided, derived from config filename.')
    parser.add_argument('-c', '--config',
                       help = 'Path to config file. If not provided, uses positional argument.')
    parser.add_argument('filepath', nargs='?',
                       help = 'Config file path (positional, optional if -c is provided)')
    
    args = parser.parse_args()
    
    # Determine config path
    if args.config:
        filepath_raw = args.config
    elif args.filepath:
        filepath_raw = args.filepath
    else:
        parser.error("Must provide either a config file path (positional argument or -c flag)")

    program_name = cc.derive_program_name_from_config(filepath_raw)
    
    # Determine pool name
    if args.pool_name:
        pool_name = args.pool_name
    else:
        pool_name = cc.derive_pool_name_from_config(program_name)
    
    current_path = os.path.dirname(__file__)
    maindir = current_path.rsplit("/",1)[0]
    config_path = cc.derive_config_path(filepath_raw, args.local, __file__)

cognito_client = cc.build_cognito_client(args.local)
sts_client = cc.build_sts_client(args.local)
AWS_REGION = cc.get_region(args.local)

def get_users(pool_id, cognito_client):
    try:
        # note that this is not strictly required in our case since we only support
        # < 5 admin users. But it is good to refactor so we can bake in that assumption
        # in a common function and improve it if necessary
        return cc.get_all_users(pool_id, cognito_client)
    except be.ClientError as err:
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
        identity_arn = "arn:aws:ses:" + AWS_REGION + ":" + account_num + ":identity/openpath@nlr.gov"
    if args.github:
        AWS_ACCT_ID = os.environ.get("AWS_ACCT_ID")
        identity_arn = "arn:aws:ses:" + AWS_REGION + ":" + AWS_ACCT_ID + ":identity/openpath@nlr.gov"
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

def format_email(program_name, map_trip_lines_enabled, columns_exclude):
    with open(maindir + '/email_automation/welcome-template.txt', 'r') as f:
        html = f.read()
        html = html.replace('<ProgramName>', program_name)
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
            'From': 'openpath@nlr.gov'
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
is_userpool_exist, pool_id = cc.get_userpool_id(pool_name, cognito_client, verbose=True)

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
            html = format_email(program_name, map_trip_lines_enabled, columns_exclude)
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
