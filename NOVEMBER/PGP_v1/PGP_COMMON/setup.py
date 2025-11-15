#!/usr/bin/env python
"""
Setup configuration for PGP_COMMON shared library package.
"""
from setuptools import setup, find_packages

setup(
    name="pgp-common",
    version="1.0.0",
    description="Shared library for PGP_v1 microservices",
    author="TelePay Development Team",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=[
        "google-cloud-secret-manager>=2.16.0",
        "google-cloud-tasks>=2.13.0",
        "cloud-sql-python-connector[pg8000]>=1.4.0",
        "pg8000>=1.29.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
