#!/usr/bin/python

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages

setup(name = 'Lexitron',
      version = '1.0',
      description = 'A regex search engine for the English language.',
      author = 'Hrothgar',
      author_email = 'hrothgarrrr@gmail.com',
      url = 'http://github.com/hrothgar/lexitron',
      license = 'GPL v2',
      packages = find_packages(),
      entry_points = {
        'console_scripts': [
          'lx = lexitron.lexitron:main'
        ]
      },
      package_data = {
        # Include the dictionary files
          '': ['*.txt']
      }
)