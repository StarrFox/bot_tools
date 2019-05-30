from setuptools import setup

setup(
	name='bot_tools',
	author='StarrFox',
	description='Tools for making discord.py bots',
	url='https://github.com/StarrFox/bot_tools',
	version="0.0.1",
	packages=['bot_tools'],
	install_requires=[
		'discord.py>=1.1.1,<2.0.0',
		'jishaku>=1.6.1,<2.0.0'],
	python_requires='>=3.6.0',
	license='MIT'
)
