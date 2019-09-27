# -*- coding: utf-8 -*-
import click
import json
import os
from shutil import copy
from lambada import models


def __get_env_vars_users(env_vars):
    env_vars_users = {}
    for x in env_vars:
        if '=' not in x:
            print('Environment variable without `=`.')
            print('Example: qlambda -e foo=var', x)
            exit(1)

        key, value = x.split('=')
        env_vars_users[key] = value

    return env_vars_users


def __get_awslambda(name, config_file):
    config = models.Config(config_file)
    if name in config.lambdas:
        lambda_config = config.lambdas[name]
        is_layer = False
    elif name in config.layers:
        lambda_config = config.layers[name]
        is_layer = True
    else:
        return None

    awsservice = models.AWSService(config.credentials, lambda_config)
    awsservice.load_role()
    awslambda = models.AWSLambda(lambda_config, awsservice, is_layer)
    missing_values = awslambda.validate()
    if len(missing_values) == 0:
        return awslambda
    
    print('Missing required missing fields:', *missing_values)
    exit(1)


@click.group()
def cli():
    pass


@cli.command()
@click.option('-n', '--name', 'name', help='Lambda name')
def init(name):
    templates_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'example',
    )

    for filename in os.listdir(templates_path):
        dest_path = os.path.join(templates_path, filename)
        copy(dest_path, '.')


@cli.command()
@click.argument('name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
@click.option('-e', '--env', 'env_vars', default=[])
def run(name, config_file, env_vars):
    config = models.Config(config_file)
    if name not in config.lambdas:
        print('Error: no lambda', name, 'found in the configuration file')
        return

    lambda_config = config.lambdas[name]
    awslambda = models.AWSLambda(lambda_config, None)

    missing_values = awslambda.validate()
    if len(missing_values) == 0:
        return awslambda
    
    print('Missing required missing fields:', *missing_values)
    exit(1)

    env_vars_users = __get_env_vars_users(env_vars)
    awslambda.run(env_vars_users)


@cli.command()
@click.argument('name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def invoke(name, config_file):
    awslambda = __get_awslambda(name, config_file)
    if awslambda is None:
        print('Error: no lambda', name, 'found in the configuration file')
        return

    response = awslambda.invoke()
    print(response)
    print('Response Payload', response['Payload'].read())


@cli.command()
@click.argument('name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def build(name, config_file):
    config = models.Config(config_file)
    if name not in config.lambdas:
        print('Error: no lambda', name, 'found in the configuration file')
        return

    lambda_config = config.lambdas[name]
    awsservice = models.AWSService(config.credentials, lambda_config)
    awsservice.load_role()
    awslambda = models.AWSLambda(lambda_config, awsservice)
    awslambda.build()


@cli.command()
@click.argument('name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def deploy(name, config_file):
    awslambda = __get_awslambda(name, config_file)
    if awslambda is None:
        print('Error: no lambda', name, 'found in the configuration file')
        return

    zip_file = awslambda.build()
    response = awslambda.deploy(zip_file)
    print(response)

    if not awslambda.is_layer and awslambda.alias is not None:
        version = response['Version']
        response = awslambda.create_update_alias(awslambda.alias, version)
        print(response)


@cli.command()
@click.argument('name')
@click.option('-v', '--version', 'version', help='Version')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def info(name, version, config_file):
    awslambda = __get_awslambda(name, config_file)
    if awslambda is None:
        print('Error: no lambda', name, 'found in the configuration file')
        return

    response, code_size, arn = awslambda.get_info(version)
    print(json.dumps(response, indent=2, sort_keys=True))
    print('Arn', code_size)
    print('CodeSize', arn)


@cli.command()
@click.argument('name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def update_config(name, config_file):
    awslambda = __get_awslambda(name, config_file)
    if awslambda is None:
        print('Error: no lambda', name, 'found in the configuration file')
        return

    response = awslambda.update_function_configuration()
    print(response)


if __name__ == '__main__':
    cli()
