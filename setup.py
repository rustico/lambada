#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md') as readme_file:
    long_description = readme_file.read()

requirements = ['Click>=7', 'boto3>=1.9', 'PyYAML>=5']

setup(
    author="Nicolas Bases",
    author_email='nmbases@protonmail.com',
    classifiers=[
        'Development Status :: 3 - Alpha',
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
    long_description=long_description,
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords='lambada',
    name='lambada-again',
    packages=find_packages(include=['lambada']),
    test_suite='tests',
    url='https://github.com/rustico/lambada',
    version='0.2.6',
    python_requires='>=3.6',
)
