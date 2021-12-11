from setuptools import setup

def is_comment(s):
    return s.lstrip().startswith("#")

requirements = []
with open('requirements.txt') as f:
  requirements = list(filter(lambda r: not is_comment(r), f.read().splitlines()))

setup(
    name='diskord-pie',
    author='Miroslav Demek',
    version='0.0.1',
    license="MIT",
    description="A simple and incomplete library for writing discord bots in python.",
    packages=['diskordpie'],
    install_requires=requirements
)
