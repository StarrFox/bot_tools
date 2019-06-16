from setuptools import setup

setup(
	name='bot_stuff',
	author='StarrFox',
	description='stuff for bots',
	url='https://github.com/StarrFox/bot_stuff',
	version="0.0.2",
	packages=['bot_stuff'],
	install_requires=[
		'discord.py>=1.1.1,<2.0.0',
		'jishaku>=1.6.1,<2.0.0'],
	python_requires='>=3.6.0',
	license='MIT'
)
