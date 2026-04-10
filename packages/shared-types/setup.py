from setuptools import setup, find_packages

setup(
    name="shared_types",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["pydantic>=2.6", "boto3>=1.34"],
)
