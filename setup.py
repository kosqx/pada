#!/usr/bin/env python

#import os
#import glob
from distutils.core import setup

# look: http://pypi.python.org/pypi?%3Aaction=list_classifiers

setup(
    name='PADA',
    version='0.5.0',
    license='LGPL',
    description='Python Advanced DB API',
    long_description='Library making eazy using Python DB API', #ToDo: reStructuredText
    author='Krzysztof Kosyl',
    author_email='krzysztof.kosyl@gmail.com',
    url='http://github.com/kosqx/pada/tree/master',
    packages=[
        'pada',
    ],

    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: SQL',
        'Topic :: Database',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
