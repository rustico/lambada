Quick Python Lambda Wrapper
===========================

DO NOT USE, TESTING
===================

A simple way to create AWS Lambda projects in Python heavily inspired
and copied from https://github.com/nficano/python-lambda

First look
----------

File structure
~~~~~~~~~~~~~~

We need to have a configuration file and a main file to call.

Basic
^^^^^

::

    $ tree

    ├── config.yaml         # Configuration file
    └── service.py          # Handler

More real
'''''''''

::

    $ tree

    ├── config.yaml         # Configuration file
    ├── event.json          # Test object that will be use to call the service
    ├── README.md
    ├── requirements.txt    # Lambda dependencies
    ├── event.py            # Test input file
    ├── service.py          # Handler
    ├── src
    │   └── lib.py
    └── venv                # Virtualenv for local testing

We can use multiples configuration files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    $ tree

    ├── config.yaml
    ├── config.qa.yaml
    ├── config.prod.yaml
    ├── requirements.txt
    └── service.py

We can have parent-child configurations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The configuration files needs to have the same name.

::

    $ tree

    ├── config.yaml
    ├── requirements.txt
    ├── lambda-test
    │   ├── config.yaml
    │   ├── README.md
    │   ├── requirements.txt
    │   └── service.py
    └── README.md

How to use it
-------------

Run locally
~~~~~~~~~~~

::

    $ qlambda run [-d root directory] [-c configuration file]
    $ qlambda run
    $ qlambda run -d lambda-to-run

Event test file
~~~~~~~~~~~~~~~

You can test the lambda locally passing an event input defined in the
configuration file as:

::

    # path to file.property
    test_event: event.input

This will look for the ``event.py`` file in the lambda directory and get
the ``input`` property from it.

::

    lambda-directory$ cat event.py
    input = {'test': 'test'}

Layers
^^^^^^

If we define a local module as a layer it will load the layer so we can
call it from our lambda. We need to have the dependencies installed in
our local virtual environment.

::

    layers:
      - ../common/config.yaml

Build
~~~~~

It will bundle all the dependencies and create a ``dist`` directory with
the zip file.

::

    $ qlambda build [-d root directory] [-c configuration file]
    $ qlambda build
    $ qlambda build -d lambda-to-build

Configuration
^^^^^^^^^^^^^

Requirements (optional)
'''''''''''''''''''''''

If there is a requirements file specified it will install the packages
locally

::

    requirements: requirements.txt

Directories (optional)
''''''''''''''''''''''

By default it will add only the directories specified in the
``directories`` section.

::

    directories                 
      - src

Files (optional) (default= all files + main file - directories)
'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''

By default it will add all the files. You can specify which ones in the
``files`` section.

::

    files:                      # Files we want to include in the root directoy 
      - config.py

Symlink
^^^^^^^

It will copy the ``symlink`` into the bundle.

Deploy
~~~~~~

It will create or update the Lambda and deploy the ``zipfile`` created
in the ``build`` step into AWS.

::

    $ qlambda deploy [-d root directory] [-c configuration file]
    $ qlambda deploy
    $ qlambda deploy -d lambda-to-run

Configuration
~~~~~~~~~~~~~

These values are required in the configuration file

::

    function_name: lambda-function-name
    description: Description
    region: us-east-1
    main_file: service.py
    handler: handler
    runtime: python3.6

    aws_access_key_id: A123456789Z            
    aws_secret_access_key: a1234567789bcdergz

Environment variables
^^^^^^^^^^^^^^^^^^^^^

::

    environment_variables:
      DB: 'postgresql://postgres:@localhost:5432/template'

Security groups and Subnets
^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    security_group_ids:
      - sg-123456789

    subnet_ids:
      - subnet-a123456789
      - subnet-b123456789

Alias
^^^^^

::

    alias: dev

Layers
^^^^^^

::

    layers:
      - ../lib/config.yaml
      - name-of-the-layer

Info
----

It will print the lambda information

::

    $ qlambda info [-d root directory] [-c configuration file]
    $ qlambda info
    $ qlambda info -d lambda

Update configuration
--------------------

It will update the lambda configuration. Useful if we did only
configuration changes.

::

    $ qlambda update_config [-d root directory] [-c configuration file]
    $ qlambda update_config
    $ qlambda update_config -d lambda

Configuration file example
~~~~~~~~~~~~~~~~~~~~~~~~~~

::

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

Layers
------

We can also ``build``, ``deploy``, ``update`` and get ``info`` on
layers.

Lambda
~~~~~~

We can define a layer dependency inside a lambda in two ways.

We can specify the name of the layer:

::

    layers:
      - name-of-the-layer

Or the directory of the layer config file

::

      - ../lib/config.yaml
      - /home/user/lib/config.yaml

In both cases it will load the Layer into the python system path
variable.

By default it will set up the last version of the layer.

You can specify a different like this:

::

    layers:
      - name-of-the-layer,1
      - ../lib/config.yaml,1

Configuration file example
~~~~~~~~~~~~~~~~~~~~~~~~~~

The main difference is the ``is_layer`` propertiy is set to ``true``.

::

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
