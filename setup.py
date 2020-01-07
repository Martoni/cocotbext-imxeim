#! /usr/bin/python3
# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------------
# Author:   Fabien Marteau <fabien.marteau@armadeus.com>
# Created:  07/01/2020
#-----------------------------------------------------------------------------
#  Copyright (2020)  Armadeus Systems
#-----------------------------------------------------------------------------
import setuptools
from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="cocotbext.imxeim",
    use_scm_version={
        "relative_to": __file__,
        "write_to": "cocotbext/imxeim/version.py",
    },
    author="Fabien Marteau",
    author_email="mail@fabienm.eu",
    description="Cocotb i.MX EIM module",
    long_description=long_description,
    url="https://github.com/Martoni/cocotbext-imxeim.git",
    packages=["cocotbext.imxeim"],
    install_requires=['cocotb'],
    setup_requires=[
        'setuptools_scm',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ],
)
