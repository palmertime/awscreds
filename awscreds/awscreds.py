import click
import boto3
import configparser
from pathlib import Path
import os

# AWS config files
home = str(Path.home())
aws_creds_file = f'{home}/.aws/credentials'


def configToDict(config, profile):
    dict = {}
    for section in config.sections():
        dict[section] = {}
        for option in config.options(section):
            dict[section][option] = config.get(section, option)
    return dict[profile]


@click.command()
@click.option('--account', '-a', help='AWS account to assume')
@click.option('--duration', '-d', help='Duration in seconds for aws session',
              default='3600', type=int)
@click.option('--profile', '-p', help='AWS profile to use', default='default')
@click.option('--role', '-r', help='AWS role to assume',
              default='OrganizationAccountAccessRole')
@click.argument('mfa', required=True)
def cli(account, duration, mfa, profile, role):
    # Get Credentials
    if not Path(aws_creds_file).exists():
        print(f'Credential file not found: {aws_creds_file}')
        creds = {}
        creds['aws_access_key_id'] = (
            click.prompt('Enter AWS Access Key'))
        creds['aws_secret_access_key'] = (
            click.prompt('Enter AWS Secret Key'))
    else:
        config = configparser.ConfigParser()
        config.read(aws_creds_file)
        creds = configToDict(config, profile)

    # Set environment variables for boto3 auth
    os.environ['AWS_ACCESS_KEY_ID'] = creds['aws_access_key_id']
    os.environ['AWS_SECRET_ACCESS_KEY'] = creds['aws_secret_access_key']
    os.environ['AWS_SESSION_TOKEN'] = ""

    # Get profile/creds username arn
    stsClient = boto3.client('sts')
    arnResult = stsClient.get_caller_identity().get('Arn')
    if not account:
        account = stsClient.get_caller_identity().get('Account')
    arn = arnResult.split('user/')[0]
    user = arnResult.split('user/')[1]
    serial = f'{arn}mfa/{user}'

    assumeRoleObject = boto3.client('sts').assume_role(
      RoleArn=f"arn:aws:iam::{account}:role/{role}",
      RoleSessionName=user,
      DurationSeconds=duration,
      SerialNumber=serial,
      TokenCode=mfa
    )

    key = (f"set -g -x AWS_ACCESS_KEY_ID "
           f"{assumeRoleObject['Credentials']['AccessKeyId']}")
    secret = (f"set -g -x AWS_SECRET_ACCESS_KEY "
              f"{assumeRoleObject['Credentials']['SecretAccessKey']}")
    session = (f"set -g -x AWS_SESSION_TOKEN "
               f"{assumeRoleObject['Credentials']['SessionToken']}")

    file = open(f"{home}/.{profile}-{role}-{account}", 'w')

    file.write(f'{key}\n')
    print(key)
    file.write(f'{secret}\n')
    print(secret)
    file.write(f'{session}\n')
    print(session)

    file.close()
