#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = ['Click>=7', 'boto3>=1.9', 'PyYAML>=5']

setup_requirements = []

test_requirements = []

setup(
    author="Nicolas Bases",
    author_email='nmbases@protonmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    description="A simple way to create AWS Lambda projects in Python heavily inspired and copied from https://github.com/nficano/python-lambda",
    entry_points={
        'console_scripts': [
            'lambada=lambada.cli:cli',
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='lambada',
    name='lambada',
    packages=find_packages(include=['lambada']),
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/rustico/lambada',
    version='0.1.0',
    zip_safe=False,
)
