from setuptools import setup

requirements = []
with open('requirements.txt') as f:
  requirements = f.read().splitlines()

setup(
    name='diskord-pie',
    author='Miroslav Demek',
    version='0.0.1',
    license="MIT",
    description="A simple and incomplete library for writing discord bots in python.",
    packages=['diskordpie'],
    install_requires=requirements
)
