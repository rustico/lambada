# -*- coding: utf-8 -*-
import click
import json
from quick_python_lambda_wrapper import models


@click.group()
def cli():
    pass


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
def run(root_dir):
    config = models.Config(root_dir)
    awslambda = models.AWSLambda(config, None, root_dir)
    awslambda.run()


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
def build(root_dir):
    config = models.Config(root_dir)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    awslambda.build()


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
def deploy(root_dir):
    config = models.Config(root_dir)
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
def info(root_dir, version):
    config = models.Config(root_dir)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    response, code_size, arn = awslambda.get_info(version)
    print(json.dumps(response, indent=2, sort_keys=True))
    print('Arn', code_size)
    print('CodeSize', arn)


@cli.command()
@click.option('-d', '--dir', 'root_dir', help='Lambda root directory', default='.')
def update_config(root_dir):
    config = models.Config(root_dir)
    awsservice = models.AWSService(config)
    awslambda = models.AWSLambda(config, awsservice, root_dir)
    response = awslambda.update_function_configuration()
    print(response)


if __name__ == '__main__':
    cli()
