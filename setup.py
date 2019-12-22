from setuptools import setup
import re

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

with open('bot_stuff/__init__.py') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

setup(
    name='bot_stuff',
    author='StarrFox',
    description='stuff for bots',
    url='https://github.com/StarrFox/bot_stuff',
    version=version,
    packages=['bot_stuff'],
    install_requires=requirements,
    python_requires='>=3.6.0',
    license='MIT'
)
