from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='Eggcelerator',
      version=version,
      description="Compiles your packages into binary eggs and caches them",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='',
      author_email='',
      url='',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      scripts=['scripts/eggcelerator'],
      install_requires=[
        'path.py',
        's3cmd',
        'argparse', # for those 2.6 throwbacks
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
