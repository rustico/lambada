import subprocess
import sys
import os.path
from time import time
from tempfile import mkdtemp
from shutil import copy
from shutil import copyfile
from shutil import copystat
from shutil import copytree
import zipfile
import importlib
import json

import yaml
import boto3


class Config():
    def __init__(self, src, filename, lambda_filename=None):
        if lambda_filename is None:
            lambda_filename = filename

        lambda_config_file = os.path.join(src, lambda_filename)
        config = self.load_config(lambda_config_file)

        if 'aws_access_key_id' not in config or 'aws_secret_access_key' not in config:
            raise ValueError('No aws_access_key_id or aws_secret_access_key')

        self.credentials = {
            'aws_access_key_id': config['aws_access_key_id'], 
            'aws_secret_access_key': config['aws_secret_access_key']
        }

        if 'lambdas' not in config:
            raise ValueError('No lambdas')

        self.lambdas = []
        self.errors = []
        for lambda_name, lambda_config in config['lambdas'].items():
            if lambda_config.get('abstract', False):
                continue

            parent = lambda_config.get('parent', None)
            if parent is not None:
                if parent not in config['lambdas']:
                    raise ValueError('Parent doesn\'t exist :(')

                parent_config = config['lambdas'][parent]
                lambda_config = self.merge_config(parent_config, lambda_config)

            lambda_missing_values = self.validate(lambda_config)
            if len(lambda_missing_values) > 0:
                self.errors.append([lambda_name, lambda_missing_values])
            else:
                self.lambdas.append(lambda_config)

        if len(self.errors) > 0:
            msg = ''
            for error in self.errors:
                error_msg = '{}: {}\n'.format(error[0], ','.join(error[1]))
                msg += error_msg

            raise ValueError(msg)

    def load_config(self, config_file):
        with open(config_file, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)

    def validate(self, lambda_config):
        missing_values = []
        required_values = ['region', 'main_file', 'handler', 'runtime', 'role', 'path', 'function_name', 'description']
        for required_value in required_values:
            if required_value not in lambda_config:
                missing_values.append(required_value)

        return missing_values

    def merge_config(self, parent, child):
        config = parent.copy()
        for key, val in child.items():
            val_type = type(val)
            if val_type == dict:
                key_values = config.get(key, {})
                config[key] = {**key_values, **val}
            elif val_type == list:
                if key in config:
                    config[key] += val
                else:
                    config[key] = val
            else:
                config[key] = val

        return config

class AWSService():
    def __init__(self, config):
        self.config = config
        self.profile_name = self.config.values.get('profile_name')
        self.aws_access_key_id = self.config.values.get('aws_access_key_id')
        self.aws_secret_access_key = self.config.values.get('aws_secret_access_key')
        self.region = self.config.values.get('region', None)
        self.bucket_name = self.config.values.get('bucket_name')

        self.role = self.config.values.get('role', 'lambda_basic_execution')
        self.account_id = self.get_account_id()
        self.role_name = 'arn:aws:iam::{0}:role/{1}'.format(self.account_id, self.role)

    def exists_lambda(self, function_name):
        client = self.get_client('lambda')

        try:
            return client.get_function(FunctionName=function_name)
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

    def get_function(self, function_name):
        client = self.get_client('lambda')
        return client.get_function(FunctionName=function_name)

    def get_layer_last_version(self, layer_name):
        layer_versions = self.get_layer_versions(layer_name)
        layer_last_version = layer_versions['LayerVersions'][0]['Version']
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

    def invoke(self, function_name, payload):
        client = self.get_client('lambda')
        return client.invoke(FunctionName=function_name, Payload=payload)



class AWSLambda():
    def __init__(self, config, awsservice, src='.'):
        self.src = src
        self.config = config
        self.awsservice = awsservice

        self.function_name = self.config.values.get('function_name')
        self.description = self.config.values.get('description', '')
        self.main_file = self.config.values.get('main_file')
        self.handler = self.config.values.get('handler')
        self.alias = self.config.values.get('alias')
        self.root_dir = self.config.values.get('root_dir')
        self.test_event = self.config.values.get('test_event')

        self.directories = self.config.values.get('directories', [])
        self.files = self.config.values.get('files')
        self.environment_variables = self.config.values.get('environment_variables', {})
        self.tags = self.config.values.get('tags', {})

        self.is_layer = self.config.values.get('is_layer', False)
        self.layer_module_name = self.config.values.get('layer_module_name')
        self.load_layers()

        self.runtime = self.config.values.get('runtime', 'python3.6')
        self.requirements_filename = self.config.values.get('requirements')
        self.timeout = self.config.values.get('timeout', 15)
        self.memory_size = self.config.values.get('memory_size', 512)

        self.subnet_ids = self.config.values.get('subnet_ids', [])
        self.security_group_ids = self.config.values.get('security_group_ids', [])

        self.dist_directory = self.config.values.get('dist_directory', 'dist')
        self.bucket_name = self.config.values.get('bucket_name')
        self.s3_filename = self.config.values.get('s3_filename')

    def load_layers(self):
        self.layers = []
        self.layers_dirs = []
        # We need to get the Layer Arn and the last version
        for layer in self.config.values.get('layers', []):
            layer_properties = layer.split(',')
            layer_name = layer_properties[0].strip()

            if (layer_name[0] == '.' or layer_name[0] == '/'):
                if(layer_name[0] == '.'):
                    layer_config_file = self.root_dir + '/' + layer_name
                else:
                    layer_config_file = layer_name

                with open(layer_config_file, 'r') as stream:
                    try:
                        layer_config_yaml = yaml.safe_load(stream)
                    except yaml.YAMLError as exc:
                        print('Error in layer config file', layer_name, exc)

                self.layers_dirs.append(os.path.dirname(layer_config_file))
                layer_name = layer_config_yaml['function_name']

            if self.awsservice is not None:
                layer_versions = self.awsservice.get_layer_versions(layer_name)
                if len(layer_versions['LayerVersions']) == 0:
                    raise ValueError('Layer doesn\'t have any version deployed', layer_name)

                layer_arn = layer_versions['LayerVersions'][0]['LayerVersionArn']

                # If there is no version specified we set the last one
                if len(layer_properties) == 2:
                    layer_version = layer_properties[1]
                    pos = layer_arn.rfind(':')
                    layer_arn = layer_arn[:pos]
                    layer_arn += ':' + layer_version

                self.layers.append(layer_arn)

    def run(self, env_vars=[]):
        # Load layers as local dependencies
        for layer in self.layers_dirs:
            sys.path.insert(0, layer)

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
        sys.path.insert(0, self.root_dir)

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
        sys.path.insert(0, self.root_dir)

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
        return self.awsservice.invoke(self.function_name, payload)

    def build(self):
        temp_path = mkdtemp(prefix='aws-lambda')
        print('temp directory', temp_path)

        self.install_packages(temp_path)
        self.copy_files(temp_path)

        dist_directory = os.path.join(self.src, self.dist_directory)
        if not os.path.exists(dist_directory):
            os.makedirs(dist_directory)

        output_filename = '{0}-{1}.zip'.format(time(), self.function_name)
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
        if self.awsservice.exists_lambda(self.function_name):
            response = self.update_function(zipfile)
        else:
            response = self.create_function(zipfile)

        return response

    def deploy_layer(self, zipfile=None, via_s3=False):
        print('publish layer', self.function_name)
        options = {
            'LayerName': self.function_name,
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
        options = {
            'FunctionName': self.function_name,
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
            'Layers': self.layers
        }

        return options

    def create_function(self, zipfile=None, via_s3=False):
        print('creating new lambda', self.function_name)
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
        print('updating lambda code', self.function_name)
        options = {
            'FunctionName': self.function_name,
            'Publish': True,
        }

        if via_s3:
            options['S3Bucket'] = self.bucket_name
            options['S3Key'] = self.s3_filename
        else:
            options['ZipFile'] = zipfile

        return self.awsservice.update_function_code(options)

    def update_function_configuration(self):
        print('updating lambda configuration', self.function_name)
        options = self.get_function_base_options()
        return self.awsservice.update_function_configuration(options)

    def install_packages(self, path):
        if self.requirements_filename is None:
            return

        requirements = os.path.join(self.src, self.requirements_filename)
        if not os.path.exists(requirements):
            sys.exit('requirements file doesn\'t exists')

        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements, '-t', path, '--ignore-installed'])

    def get_info(self, version=1):
        if self.is_layer:
            response = self.awsservice.get_layer(self.function_name, version)
            code_size = response['Content']['CodeSize']
            arn = response['LayerArn']
        else:
            response = self.awsservice.get_function(self.function_name)
            code_size = response['Configuration']['CodeSize']
            arn = response['Configuration']['FunctionArn']

        return response, code_size, arn

    def copy_packages(self, path):
        pass

    def copy_files(self, path):
        main_file_path = os.path.join(self.src, self.main_file)
        files = [main_file_path]
        for filename in os.listdir(self.src):
            filepath = os.path.join(self.src, filename)
            if os.path.isdir(filepath) and filename in self.directories:
                files.append(filepath)
            elif not os.path.isdir(filepath) and self.files is None :
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
        alias = self.awsservice.get_alias(self.function_name, name)
        if alias is None:
            response = self.awsservice.create_alias(self.function_name, name, version)
        else:
            response = self.awsservice.update_alias(self.function_name, name, version)

        return response
