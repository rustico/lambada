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

def _get_lambda_config(name, config):
    is_layer = False
    if name == '':
        if len(config.lambdas) == 1:
            lambdas_configs = list(config.lambdas.values())
            lambda_config = lambdas_configs[0]
        elif len(config.layers) == 1 and len(config.lambdas) == 0:
            lambda_config = list(config.layers.values())[0]
            is_layer = True
        else:
            click.echo('- Lambdas -')
            for i, name in enumerate(config.lambdas.keys()):
                click.echo('{}){}'.format(i, name))

            click.echo('- Layers -')
            from_ = ord('a')
            for i, name in enumerate(config.layers.keys()):
                click.echo('{}){}'.format(chr(i + from_), name))

            value = click.prompt('More than one Lambda/Layer. Please select which')
            if value.isalpha():
                number = ord(value)
                if number < 0 or number > len(config.layers):
                    click.echo('Layer doesn\'t exists')
                    exit(1)

                pos = number - from_ + len(config.lambdas)
                lambda_config = list(config.layers.values())[pos]
                is_layer = True
            else:
                value = int(value)
                if value < 0 or value > len(config.lambdas):
                    click.echo('Lambda doesn\'t exists')
                    exit(1)

                lambdas_configs = list(config.lambdas.values())
                lambda_config = lambdas_configs[value]

    else:
        if name in config.lambdas:
            lambda_config = config.lambdas[name]
        elif name in config.layers:
            lambda_config = config.layers[name]
            is_layer = True
        else:
            print('Error: no lambda', name, 'found in the configuration file')
            exit(1)

    return lambda_config, is_layer

def __get_awslambda(name, config_file):
    config = models.Config(config_file)
    lambda_config, is_layer = _get_lambda_config(name, config)
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


@cli.command(help='Create basic project structure')
@click.option('-n', '--name', 'name', help='Lambda name')
def init(name):
    templates_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'example',
    )

    for filename in os.listdir(templates_path):
        dest_path = os.path.join(templates_path, filename)
        copy(dest_path, '.')

    print('Tip: add `config.yaml` to the .gitignore file')


@cli.command(help='Run lambda locally')
@click.option('-n', '--name', default='', help='Lambda name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
@click.option('-e', '--env', 'env_vars', multiple=True)
def run(name, config_file, env_vars):
    config = models.Config(config_file)
    lambda_config, is_layer = _get_lambda_config(name, config)
    awslambda = models.AWSLambda(lambda_config, None)
    missing_values = awslambda.validate()
    if len(missing_values) > 0:
        print('Missing required missing fields:', *missing_values)
        exit(1)

    env_vars_users = __get_env_vars_users(env_vars)
    awslambda.run(env_vars_users)


@cli.command(help='Invoke lambda remotely')
@click.argument('name')
@click.option('-n', '--name', default='', help='Lambda name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def invoke(name, config_file):
    awslambda = __get_awslambda(name, config_file)
    response = awslambda.invoke()
    print(response)
    print('Response Payload', response['Payload'].read())


@cli.command(help='Build lambda/layer locally')
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


@cli.command(help='Deploy lambda/layer')
@click.option('-n', '--name', default=None, help='Lambda name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def deploy(name, config_file):
    if name is None:
        doyouwant = input('Do you want to deploy all lambdas/layers? [NO]: ')
        if doyouwant is None or doyouwant.lower() not in ('yes', 'y'):
            print('Not deploying. Confirmation answers: yes, y')
            return

        config = models.Config(config_file)
        deployed = []
        for layer_name in config.layers.keys():
            print(layer_name)
            awslambda = __get_awslambda(layer_name, config_file)
            zip_file = awslambda.build()
            response = awslambda.deploy(zip_file)
            print(response)
            deployed.append(layer_name)

        for lambda_name in config.lambdas.keys():
            print(lambda_name)
            awslambda = __get_awslambda(lambda_name, config_file)
            zip_file = awslambda.build()
            response = awslambda.deploy(zip_file)
            print(response)
            deployed.append(lambda_name)

        print('Deployed', deployed)
    else:
        awslambda = __get_awslambda(name, config_file)
        zip_file = awslambda.build()
        response = awslambda.deploy(zip_file)
        print(response)

    if not awslambda.is_layer and awslambda.alias is not None:
        version = response['Version']
        response = awslambda.create_update_alias(awslambda.alias, version)
        print(response)


@cli.command(help='Get information about Lambda/Layer from AWS')
@click.argument('name')
@click.option('-v', '--version', 'version', help='Version')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def info(name, version, config_file):
    awslambda = __get_awslambda(name, config_file)
    response, code_size, arn = awslambda.get_info(version)
    print(json.dumps(response, indent=2, sort_keys=True))
    print('Arn', code_size)
    print('CodeSize', arn)


@cli.command(help='Update lambda configuration')
@click.argument('name')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def update_config(name, config_file):
    awslambda = __get_awslambda(name, config_file)
    response = awslambda.update_function_configuration()
    print(response)


if __name__ == '__main__':
    cli()
