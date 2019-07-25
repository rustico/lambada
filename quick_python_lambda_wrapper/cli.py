# -*- coding: utf-8 -*-
import click
import json
from quick_python_lambda_wrapper import models


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


@click.group()
def cli():
    pass


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
@click.option('-e', '--env', 'env_vars', multiple=True)
def run(root_dir, config_file, env_vars):
    config = models.Config(root_dir, config_file)
    awslambda = models.AWSLambda(config, None, root_dir)
    env_vars_users = __get_env_vars_users(env_vars)
    awslambda.run(env_vars_users)


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def invoke(root_dir, config_file):
    config = models.Config(root_dir, config_file)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    response = awslambda.invoke()
    print(response)
    print('Response Payload', response['Payload'].read())


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def build(root_dir, config_file):
    config = models.Config(root_dir, config_file)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    awslambda.build()


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def deploy(root_dir, config_file):
    config = models.Config(root_dir, config_file)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    zip_file = awslambda.build()
    response = awslambda.deploy(zip_file)
    print(response)

    if not awslambda.is_layer and awslambda.alias is not None:
        version = response['Version']
        response = awslambda.create_update_alias(awslambda.alias, version)
        print(response)


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
@click.option('-v', '--version', 'version', help='Version')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def info(root_dir, version, config_file):
    config = models.Config(root_dir, config_file)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    response, code_size, arn = awslambda.get_info(version)
    print(json.dumps(response, indent=2, sort_keys=True))
    print('Arn', code_size)
    print('CodeSize', arn)


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
@click.option('-c', '--config', 'config_file', help='Configuration file', default='config.yaml')
def update_config(root_dir, config_file):
    config = models.Config(root_dir, config_file)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    response = awslambda.update_function_configuration()
    print(response)


if __name__ == '__main__':
    cli()
