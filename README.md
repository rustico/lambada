# Lambada
# DO NOT USE, TESTING

A simple way to create AWS Lambda projects in Python heavily inspired and copied from https://github.com/nficano/python-lambda

# Basic Usage
A basic lambda without dependencies.

``` 
$ tree

├── config.yaml         # Configuration file
└── service.py          # Handler
```

### Run
```
$ lambada run
```

### Invoke remotely
```
$ lambada invoke
```

### Deploy
```
$ lambada deploy 
$ lambada deploy -c config.qa.yaml
$ lambada deploy -c config.prod.yaml
```

If there is a layer associated to the lambda in the `config.yaml` without a version specified it will update it with the last one.

### Update lambda configuration
```
$ lambada update-config
$ lambada update-config -c config.qa.yaml
$ lambada update-config -c config.prod.yaml
```
If there is a layer associated to the lambda in the `config.yaml` without a version specified it will update it with the last one.

### Build
```
$ lambada build
```
It will create a zip file in the `./dist` directory


## File structure
We need to have a configuration file and a main file to call.

### With multiples configuration files
``` 
$ tree

├── config.yaml
├── config.qa.yaml
├── config.prod.yaml
├── requirements.txt
└── service.py
```

### We can have parent-child configurations
The configuration files needs to have the same name. It will build only the `requirements.txt` at the lambda directory.

``` 
$ tree

├── config.yaml
├── requirements.txt
├── lambda-A
│   ├── config.yaml
│   ├── README.md
│   ├── requirements.txt
│   └── service.py
├── lambda-B
│   ├── config.yaml
│   ├── README.md
│   ├── requirements.txt
│   └── service.py
├── requirements.txt
└── README.md
```

And we need to execute the commands in the parent directory and specify the directory of the lambda with `-d`.
```
$ lambada run -d lambda-A
$ lambada deploy -d lambda-A -c config.prod.yaml
$ lambada invoke -d lambda-A -c config.prod.yaml
```

## How to use it

### Run locally
```
$ lambada run [-d root directory] [-c configuration file]
$ lambada run
$ lambada run -d lambda-to-run
```

#### Configuration

##### Event test file (optional)
You can test the lambda locally passing an event input defined in the configuration file as:

```
# path to file.property
test_event: event.input
```

This will look for the `event.py` file in the lambda directory and get the `input` property from it.
```
lambda-directory$ cat event.py
input = {'test': 'test'}
```

##### Layers (optional)
If we define a local module as a layer it will load the layer so we can call it from our lambda.

```
layers:
  - ../common/config.yaml
```
We need to have the dependencies installed in our local virtual environment.

#### Environment vars
You can pass and override environment variables in the config.yaml using the `-e` option.
```
$ lambada run -e var1=value1 -e var2=value2
```

### Invoke remotly
```
$ lambada invoke [-d root directory] [-c configuration file]
$ lambada invoke
$ lambada invoke -d lambda-to-run
```

### Build
It will bundle all the dependencies and create a `dist` directory with the zip file.

```
$ lambada build [-d root directory] [-c configuration file]
$ lambada build
$ lambada build -d lambda-to-build
```

#### Configuration

##### Requirements (optional)
If there is a requirements file specified it will install the packages locally
```
requirements: requirements.txt
```

##### Directories (optional)
By default it will add only the directories specified in the `directories` section.
```
directories                 
  - src
```

##### Files (optional) (default= all files + main file - directories)
By default it will add all the files. You can specify which ones in the `files` section.
```
files:                      # Files we want to include in the root directoy 
  - config.py
```

#### Symlink
It will copy the `symlink` into the bundle.

### Deploy
It will create or update the Lambda and deploy the `zipfile` created in the `build` step into AWS.

```
$ lambada deploy [-d root directory] [-c configuration file]
$ lambada deploy
$ lambada deploy -d lambda-to-run
```

### Configuration
These values are required in the configuration file

```
function_name: lambda-function-name
description: Description
region: us-east-1
main_file: service.py
handler: handler
runtime: python3.6
role: lambda_basic_execution

aws_access_key_id: A123456789Z            
aws_secret_access_key: a1234567789bcdergz
```

#### Default values
```
main_file: service.py
handler: handler
runtime: python3.6
role: lambda_basic_execution
```

#### Environment variables
```
environment_variables:
  DB: 'postgresql://postgres:@localhost:5432/template'
```

#### Security groups and Subnets
```
security_group_ids:
  - sg-123456789

subnet_ids:
  - subnet-a123456789
  - subnet-b123456789
```

#### Alias
```
alias: dev
```

#### Layers
```
layers:
  - ../lib/config.yaml
  - name-of-the-layer
```

## Info
It will print the lambda information

```
$ lambada info [-d root directory] [-c configuration file]
$ lambada info
$ lambada info -d lambda
```

## Update configuration
It will update the lambda configuration. Useful if we did only configuration changes.

```
$ lambada update_config [-d root directory] [-c configuration file]
$ lambada update_config
$ lambada update_config -d lambda
```

### Configuration file example
```
$ cat config.yaml
function_name: lambda-function-name
description: Description
region: us-east-1
main_file: service.py       # Main file
handler: handler            # Main method
runtime: python3.6
is_layer: false             # Default is False

# Credentials we need for deploying the Lambda
aws_access_key_id: A123456789Z            
aws_secret_access_key: a1234567789bcdergz

# Experimental Environment variables
environment_variables:
  DB: 'postgresql://postgres:@localhost:5432/template'

# path to file.property
test_event: event.input

requirements: requirements.txt

security_group_ids:
  - sg-123456789

subnet_ids:
  - subnet-a123456789
  - subnet-b123456789

alias: dev

directories                 # Directories we want to deploy
  - src

files:                      # Files we want to include that are in the root directoy 
  - config.py

# We can specify a local layer or a remote layer
layers:
  - ../lib/config.yaml
  - name-of-the-layer
```

## Layers
We can also `build`, `deploy`, `update` and get `info` on layers.

### Lambda
We can define a layer dependency inside a lambda in two ways.

We can specify the name of the layer:
```
layers:
  - name-of-the-layer
```

Or the directory of the layer config file
```
  - ../lib/config.yaml
  - /home/user/lib/config.yaml
```

In both cases it will load the Layer into the python system path variable.

By default it will set up the last version of the layer.

You can specify a different like this:
```
layers:
  - name-of-the-layer,1
  - ../lib/config.yaml,1
```

### Configuration file example
The main difference is the `is_layer` propertiy is set to `true`.

```
function_name: layer_name
description: Description
is_layer: true
region: us-east-1
main_file: service.py
handler: handler
runtime: python3.6

requirements: requirements.txt
files:
  - utils.py

directories: 
  - lib

aws_access_key_id: A123456789Z            
aws_secret_access_key: a1234567789bcdergz
```
