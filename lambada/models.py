import subprocess
import sys
import os.path
from time import time
from tempfile import mkdtemp
from shutil import copyfile
from shutil import copystat
from shutil import copytree
import zipfile
import importlib
import json
import copy

import yaml
import boto3


class Config():
    def __init__(self, filename='config.yaml', root_dir='.'):
        lambda_config_file = os.path.join(root_dir, filename)
        config = self.load_config(lambda_config_file)

        if 'parent' in config:
            base_config_file = os.path.join(root_dir, config['parent'])
            base_config = self.load_config(base_config_file)
            self.merge_config(base_config, config)
            config = base_config

        if 'aws_access_key_id' not in config or 'aws_secret_access_key' not in config:
            raise ValueError('No aws_access_key_id or aws_secret_access_key')

        self.credentials = {
            'aws_access_key_id': config['aws_access_key_id'],
            'aws_secret_access_key': config['aws_secret_access_key']
        }

        self.layers = config.get('layers', {})
        self.parents = {}
        for lambda_name, lambda_config in config.get('lambdas', {}).items():
            if lambda_config.get('abstract', False):
                self.parents[lambda_name] = lambda_config

        self.lambdas = {}
        for lambda_name, lambda_config in config.get('lambdas', {}).items():
            if lambda_config.get('abstract', False):
                continue

            parent_name = lambda_config.get('parent', None)
            if parent_name is not None:
                if parent_name not in self.parents:
                    raise ValueError('Parent doesn\'t exist :(. Check if it has abstract: True')

                parent_config = copy.deepcopy(self.parents[parent_name])
                self.merge_config(parent_config, lambda_config)
                lambda_config = parent_config

            layers_names = lambda_config.get('layers', [])

            lambda_config['layers'] = {}
            for layer_name in layers_names:
                if ',' in layer_name:
                    layer_name, layer_version = layer_name.split(',')
                else:
                    layer_version = None

                layer_name = layer_name.strip()
                layer = self.layers[layer_name]
                if layer_version is not None:
                    layer['version'] = int(layer_version)

                lambda_config['layers'][layer_name] = layer

            self.lambdas[lambda_name] = lambda_config

    def load_config(self, config_file):
        with open(config_file, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

    def merge_config(self, parent, child):
        for key, val in child.items():
            if isinstance(val, dict):
                if key in parent:
                    key_values = parent[key]
                    self.merge_config(key_values, val)
                else:
                    parent[key] = val
            elif isinstance(val, list):
                if key in parent:
                    parent[key] += val
                else:
                    parent[key] = val
            else:
                parent[key] = val


class AWSService():
    def __init__(self, credentials, config):
        self.config = config
        self.aws_access_key_id = credentials.get('aws_access_key_id')
        self.aws_secret_access_key = credentials.get('aws_secret_access_key')
        self.profile_name = self.config.get('profile_name')
        self.region = self.config.get('region', None)
        self.bucket_name = self.config.get('bucket_name')

    def load_role(self):
        self.role = self.config.get('role', 'lambda_basic_execution')
        self.account_id = self.get_account_id()
        self.role_name = 'arn:aws:iam::{0}:role/{1}'.format(self.account_id, self.role)

    def exists_lambda(self, name):
        client = self.get_client('lambda')

        try:
            return client.get_function(FunctionName=name)
        except client.exceptions.ResourceNotFoundException as e:
            if 'Function not found' in str(e):
                return False

    def get_client(self, client):
        boto3.setup_default_session(
            profile_name=self.profile_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region,
        )
        return boto3.client(client)

    def get_account_id(self):
        """Query STS for a users' account_id"""
        client = self.get_client('sts')
        return client.get_caller_identity().get('Account')

    def create_function(self, options):
        """Register and upload a function to AWS Lambda."""
        client = self.get_client('lambda')
        options['Role'] = self.role_name
        return client.create_function(**options)

    def update_function_code(self, options):
        client = self.get_client('lambda')
        return client.update_function_code(**options)

    def update_function_configuration(self, options):
        client = self.get_client('lambda')
        return client.update_function_configuration(**options)

    def publish_layer(self, options):
        client = self.get_client('lambda')
        return client.publish_layer_version(**options)

    def get_layer(self, layer_name, version_number):
        client = self.get_client('lambda')
        return client.get_layer_version(LayerName=layer_name, VersionNumber=version_number)

    def get_layer_versions(self, layer_name):
        client = self.get_client('lambda')
        return client.list_layer_versions(LayerName=layer_name)

    def get_function(self, name):
        client = self.get_client('lambda')
        return client.get_function(FunctionName=name)

    def get_layer_last_version(self, layer_name):
        layer_versions = self.get_layer_versions(layer_name)
        layer_version = layer_versions['LayerVersions'][0]['Version']
        return layer_version

    def get_alias(self, function_name, name):
        client = self.get_client('lambda')
        try:
            alias = client.get_alias(FunctionName=function_name, Name=name)
            return alias
        except client.exceptions.ResourceNotFoundException as e:
            if 'Function not found' in str(e):
                return None

    def create_alias(self, function_name, name, version):
        client = self.get_client('lambda')
        return client.create_alias(FunctionName=function_name, Name=name, FunctionVersion=version)

    def update_alias(self, function_name, name, version):
        client = self.get_client('lambda')
        return client.update_alias(FunctionName=function_name, Name=name, FunctionVersion=version)

    def invoke(self, name, payload):
        client = self.get_client('lambda')
        return client.invoke(FunctionName=name, Payload=payload)


class AWSLambda():
    def __init__(self, config, awsservice, is_layer=False):
        self.config = config
        self.awsservice = awsservice

        self.src = self.config.get('path', '.')
        self.description = self.config.get('description', '')
        self.main_file = self.config.get('main_file')
        self.handler = self.config.get('handler')
        self.alias = self.config.get('alias')
        self.test_event = self.config.get('test_event')

        self.directories = self.config.get('directories', [])
        self.files = self.config.get('files')
        self.environment_variables = self.config.get('environment_variables', {})
        self.tags = self.config.get('tags', {})
        self.name = self.config.get('name')

        self.is_layer = is_layer
        if not is_layer:
            self.name = self.config.get('name')
            self.layers = self.config['layers']
            self.load_layers()

        self.runtime = self.config.get('runtime', 'python3.6')
        self.requirements_filename = self.config.get('requirements')
        self.timeout = self.config.get('timeout', 15)
        self.memory_size = self.config.get('memory_size', 512)

        self.subnet_ids = self.config.get('subnet_ids', [])
        self.security_group_ids = self.config.get('security_group_ids', [])

        self.dist_directory = self.config.get('dist_directory', 'dist')
        self.bucket_name = self.config.get('bucket_name')
        self.s3_filename = self.config.get('s3_filename')

    def validate(self):
        required_values = ['region', 'runtime', 'path', 'name', 'description']
        if not self.is_layer:
            required_values += ['main_file', 'handler', 'role']

        missing_values = []
        for required_value in required_values:
            if required_value not in self.config:
                missing_values.append(required_value)

        return missing_values

    def load_layers(self):
        # We need to get the Layer Arn and the last version
        for _, layer_properties in self.layers.items():
            if self.awsservice is not None and 'arn' not in layer_properties:
                layer_name = layer_properties['name']
                layer_versions = self.awsservice.get_layer_versions(layer_name)
                if len(layer_versions['LayerVersions']) == 0:
                    raise ValueError('Layer doesn\'t have any version deployed', layer_name)

                layer_arn = layer_versions['LayerVersions'][0]['LayerVersionArn']

                if 'version' in layer_properties:
                    layer_arn = '.'.join(layer_arn.split(':')[:-1])
                    layer_arn += ':' + str(layer_properties['version'])

                layer_properties['name'] = layer_name
                layer_properties['arn'] = layer_arn

    def run(self, env_vars=[]):
        # Load layers as local dependencies
        for layer_name, layer in self.layers.items():
            sys.path.insert(0, layer['path'])

        # Load environment variables
        for key, value in self.environment_variables.items():
            if type(value) != str:
                raise ValueError('Environment variable value needs to be a string', key, value)
            os.environ[key] = value

        for key, value in env_vars.items():
            if type(value) != str:
                raise ValueError('Environment variable value needs to be a string', key, value)
            os.environ[key] = value

        # Load main file and test event
        sys.path.insert(0, self.src)

        # Load event test input
        if self.test_event is not None:
            test_event_properties = self.test_event.split('.')
            test_file = test_event_properties[0]
            test_module = importlib.import_module(test_file)
            test_property = test_event_properties[1]
            test_event = getattr(test_module, test_property)
        else:
            test_event = None

        # Load main module
        main_filename = os.path.splitext(self.main_file)[0]
        module = importlib.import_module(main_filename)

        # We move to the lambda directory
        os.chdir(self.src)
        getattr(module, self.handler)(test_event, None)

    def invoke(self):
        sys.path.insert(0, self.src)

        # Load event test input
        if self.test_event is not None:
            test_event_properties = self.test_event.split('.')
            test_file = test_event_properties[0]
            test_module = importlib.import_module(test_file)
            test_property = test_event_properties[1]
            test_event = getattr(test_module, test_property)
        else:
            test_event = ''

        payload = str.encode(json.dumps(test_event))
        return self.awsservice.invoke(self.name, payload)

    def build(self):
        temp_path = mkdtemp(prefix='aws-lambda')
        print('temp directory', temp_path)

        self.install_packages(temp_path)
        self.copy_files(temp_path)

        dist_directory = os.path.join(self.src, self.dist_directory)
        if not os.path.exists(dist_directory):
            os.makedirs(dist_directory)

        output_filename = '{0}-{1}.zip'.format(time(), self.name)
        zip_file = self.archive(temp_path, dist_directory, output_filename)
        print('zip file', zip_file)
        return zip_file

    def deploy(self, zipfile):
        with open(zipfile, mode='rb') as f:
            zipfile = f.read()

        if self.is_layer:
            response = self.deploy_layer(zipfile)
            print('Arn', response['LayerArn'])
            print('CodeSize', response['Content']['CodeSize'])
        else:
            response = self.deploy_function(zipfile)

        return response

    def deploy_function(self, zipfile):
        if self.awsservice.exists_lambda(self.name):
            response = self.update_function(zipfile)
        else:
            response = self.create_function(zipfile)

        return response

    def deploy_layer(self, zipfile=None, via_s3=False):
        print('publish layer', self.name)
        options = {
            'LayerName': self.name,
            'Description': self.description,
            'CompatibleRuntimes': [self.runtime]
        }

        if via_s3:
            options['Content'] = {'S3Bucket': self.bucket_name, 'S3Key': self.s3_filename}
        else:
            options['Content'] = {'ZipFile': zipfile}

        return self.awsservice.publish_layer(options)

    def get_function_base_options(self):
        main_filename = os.path.splitext(self.main_file)[0]
        layers_arn = []
        for layer_name, layer_properties in self.layers.items():
            layers_arn.append(layer_properties['arn'])

        options = {
            'FunctionName': self.name,
            'Runtime': self.runtime,
            'Handler': '{}.{}'.format(main_filename, self.handler),
            'Description': self.description,
            'Timeout': self.timeout,
            'MemorySize': self.memory_size,
            'VpcConfig': {
                'SubnetIds': self.subnet_ids,
                'SecurityGroupIds': self.security_group_ids
            },
            'Environment': {'Variables': self.environment_variables},
            'Layers': layers_arn
        }

        return options

    def create_function(self, zipfile=None, via_s3=False):
        print('creating new lambda', self.name)
        options = self.get_function_base_options()
        options['Publish'] = True
        options['Tags'] = self.tags

        if via_s3:
            options['Code'] = {'S3Bucket': self.bucket_name, 'S3Key': self.s3_filename}
        else:
            options['Code'] = {'ZipFile': zipfile}

        return self.awsservice.create_function(options)

    def update_function(self, zipfile=None, via_s3=False):
        response_code = self.update_function_code(zipfile, via_s3)
        response_configuration = self.update_function_configuration()

        return response_configuration

    def update_function_code(self, zipfile=None, via_s3=False):
        print('updating lambda code', self.name)
        options = {
            'FunctionName': self.name,
            'Publish': True,
        }

        if via_s3:
            options['S3Bucket'] = self.bucket_name
            options['S3Key'] = self.s3_filename
        else:
            options['ZipFile'] = zipfile

        return self.awsservice.update_function_code(options)

    def update_function_configuration(self):
        print('updating lambda configuration', self.name)
        options = self.get_function_base_options()
        return self.awsservice.update_function_configuration(options)

    def install_packages(self, path):
        if self.requirements_filename is None:
            return

        requirements = os.path.join(self.src, self.requirements_filename)
        if not os.path.exists(requirements):
            print('Warning: requirements file doesn\'t exists', requirements)
        else:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements, '-t', path, '--ignore-installed'])

    def get_info(self, version=1):
        if self.is_layer:
            response = self.awsservice.get_layer(self.name, version)
            code_size = response['Content']['CodeSize']
            arn = response['LayerArn']
        else:
            response = self.awsservice.get_function(self.name)
            code_size = response['Configuration']['CodeSize']
            arn = response['Configuration']['FunctionArn']

        return response, code_size, arn

    def copy_packages(self, path):
        pass

    def copy_files(self, path):
        if self.is_layer:
            files = []
        else:
            main_file_path = os.path.join(self.src, self.main_file)
            files = [main_file_path]

        for filename in os.listdir(self.src):
            filepath = os.path.join(self.src, filename)
            if os.path.isdir(filepath) and filename in self.directories:
                files.append(filepath)
            elif not os.path.isdir(filepath) and self.files is None:
                files.append(filepath)
            elif not os.path.isdir(filepath) and self.files is not None and filename in self.files:
                files.append(filepath)

        for f in files:
            _, filename = os.path.split(f)
            destination = os.path.join(path, filename)
            if os.path.isfile(f):
                copyfile(f, destination)
                copystat(f, destination)
            elif os.path.isdir(f):
                copytree(f, destination)

    def archive(self, src, dest, filename):
        # Zip without structure
        # https://stackoverflow.com/questions/27991745/zip-file-and-avoid-directory-structure
        output = os.path.join(dest, filename)
        zfh = zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED)

        for root, directory, files in os.walk(src):
            for f in files:
                filepath = os.path.join(root, f)
                parentpath = os.path.relpath(filepath, src)
                arcname = parentpath
                if self.is_layer:
                    arcname = os.path.join('python', parentpath)

                zfh.write(filepath, arcname)

        zfh.close()
        return os.path.join(dest, filename)

    def create_update_alias(self, name, version):
        alias = self.awsservice.get_alias(self.name, name)
        if alias is None:
            response = self.awsservice.create_alias(self.name, name, version)
        else:
            response = self.awsservice.update_alias(self.name, name, version)

        return response
