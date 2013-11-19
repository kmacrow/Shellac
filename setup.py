#!/usr/bin/env python

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages

setup(name='Shellac',
      version='0.1.0',
      description='Shellac Web Accelerator',
      author='Kalan MacRow',
      author_email='kalanwm@cs.ubc.ca',
      license='MIT',
      url='https://github.com/kmacrow/Shellac',
      download_url='https://github.com/kmacrow/Shellac/releases',
      packages=find_packages('src/python'),
      package_dir={'shellac': 'src/python/shellac'},
      install_requires=['http-parser>=0.8.3', 'pylibmc>=1.2.2'],
      entry_points = {
        'console_scripts': [
            'shellac = shellac.server.Server:main'
        ]
      }
     )
