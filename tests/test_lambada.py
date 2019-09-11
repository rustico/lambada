import unittest
from lambada import models
from unittest.mock import MagicMock


class TestLambadaConfig(unittest.TestCase):
    def test_load_basic_config(self):
        # Basic with AWS credentials
        # config.0.yaml
        config = models.Config('./tests', 'config.0.yaml')
        self.assertTrue('aws_access_key_id' in config.credentials)
        self.assertTrue('aws_secret_access_key' in config.credentials)

    def test_load_config_without_aws_creds(self):
        # Basic without AWS credentials raise error
        # config.1.yaml
        with self.assertRaises(ValueError):
            models.Config('./tests', 'config.1.yaml')

    def test_load_config_check_lambdas(self):
        # Check the numbers of lambdas
        # config.2.yaml
        config = models.Config('./tests', 'config.2.yaml')
        lambdas_total = len(config.lambdas.keys())
        self.assertEqual(lambdas_total, 2)

    def test_load_config_check_lambda_values(self):
        # Check some basic values
        # config.3.yaml
        config = models.Config('./tests', 'config.3.yaml')
        self.assertEqual(config.lambdas['lambda-1']['function_name'], 'function name test')
        self.assertEqual(config.lambdas['lambda-1']['description'], 'function description')
        self.assertEqual(config.lambdas['lambda-1']['path'], '.')

    def test_load_config_check_lambda_inheritance(self):
        # Check values from parent
        # config.4.yaml
        config = models.Config('./tests', 'config.4.yaml')
        self.assertEqual(config.lambdas['lambda-test']['test_event'], 'event.input_2')
        self.assertEqual(config.lambdas['lambda-test']['environment_variables']['DB'], 'postgresql://postgres:@localhost:5432/template')
        self.assertEqual(config.lambdas['lambda-test']['subnet_ids'][0], 'subnet-1')
        self.assertEqual(config.lambdas['lambda-test']['subnet_ids'][1], 'subnet-2')
        self.assertEqual(config.lambdas['lambda-test']['role'], 'lambda-role')

    def test_load_config_raise_lambda_error_no_existint_parent(self):
        # Check error when inherit from a non existent parent (like real life)
        # config.5.yaml
        with self.assertRaises(ValueError):
            models.Config('./tests', 'config.5.yaml')

    def test_load_config_check_lambda_required_values(self):
        # Check lambda required values
        # config.6.yaml
        with self.assertRaises(ValueError):
            models.Config('./tests', 'config.6.yaml')


class TestLambadaService(unittest.TestCase):
    def test_dummy(self):
        config = models.Config('./tests', 'config.4.yaml')
        lambda_config = config.lambdas['lambda-test']
        awsservice = models.AWSService(config.credentials, lambda_config)
        awsservice.get_account_id = MagicMock(return_value=1)
        awsservice.load_role()
        self.assertEqual(awsservice.aws_access_key_id, 'access_key_id')
        self.assertEqual(awsservice.aws_secret_access_key, 'secret_access_key')
        self.assertEqual(awsservice.region, 'us-east-1')
        self.assertEqual(awsservice.role_name, 'arn:aws:iam::1:role/lambda-role')


class TestLambadaLambda(unittest.TestCase):
    def test_dummy(self):
        return
        config = models.Config('./tests', 'config.4.yaml')
        lambda_config = config.lambdas['lambda-test']
        awsservice = models.AWSService(config.credentials, lambda_config)
        awsservice.get_account_id = MagicMock(return_value=1)
        awsservice.get_layer_versions = MagicMock(return_value={'LayerVersions': [{'LayerVersionArn': 1}]})
        awslambda = models.AWSLambda(lambda_config, awsservice)
        self.assertEqual(awslambda.function_name, 'function name test')
