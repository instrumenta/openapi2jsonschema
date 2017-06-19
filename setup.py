from setuptools import setup

setup(
    name='openapi2jsonschema',
    author='Gareth Rushgrove',
    author_email='gareth@morethanseven.net',
    version='0.2.0',
    license='Apache License 2.0',
    packages=['openapi2jsonschema',],
    install_requires=[
        'jsonref',
        'pyyaml',
        'click',
        'colorama',
    ],
    tests_require=[

    ],
    entry_points={
        'console_scripts': [
            'openapi2jsonschema = openapi2jsonschema.command:default'
       ]
    },
    keywords = 'openapi, jsonschema',
    description = 'A utility to extract JSON Schema from a valid OpenAPI specification.',
    url = "https://github.com/garethr/openapi2jsonschema/",
)
