from setuptools import setup
from labnode_async import VERSION

with open('README.md', 'r') as f:
    long_description = f.read()


setup(
   name='labnode_async',
   version=VERSION,
   author='Patrick Baus',
   author_email='patrick.baus@physik.tu-darmstadt.de',
   url='https://github.com/PatrickBaus/LabNode',
   description='An AsyncIO implementation for the Labnode API',
   long_description=long_description,
   classifiers=[
    'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
    'Programming Language :: Python',
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Natural Language :: English',
    'Topic :: Home Automation',
   ],
   keywords='Labnode API',
   license='GPL',
   license_files=('LICENSE',),
   packages=['labnode_async'],  # same as name
   install_requires=['cobs', 'cbor2' ],  # external packages as dependencies
)
