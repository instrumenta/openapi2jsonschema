# openapi2jsonschema

A utility to extract [JSON Schema](http://json-schema.org/) from a
valid [OpenAPI](https://www.openapis.org/) specification.


## Why

OpenAPI contains a list of type `definitions` using a superset of JSON
Schema. These are used internally by various OpenAPI compatible tools. I
found myself however wanting to use those schemas separately, outside
existing OpenAPI tooling. Generating separate schemas for types defined
in OpenAPI allows for all sorts of indepent tooling to be build which
can be easily maintained, because the canonical definition is shared.


## Installation

`openapi2jsonschema` is implemented in Python. Assuming you have a
Python intepreter and pip installed you should be able to install with:

```
pip install openapi2jsonschema
```

This has not yet been widely tested and is currently in a _works on my
machine_ state.


## Usage

The simplest usage is to point the `openapi2jsonschema` tool at a URL
containing a JSON (or YAML) OpenAPI definition like so:

```
openapi2jsonschema https://raw.githubusercontent.com/kubernetes/kubernetes/master/api/openapi-spec/swagger.json
```

This will generate a set of schemas in a `schemas` directory. The tool
provides a number of options to modify the output:

```
$ openapi2jsonschema --help
Usage: openapi2jsonschema [OPTIONS] SCHEMA

  Converts a valid OpenAPI specification into a set of JSON Schema files

Options:
  -o, --output PATH  Directory to store schema files
  -p, --prefix TEXT  Prefix for JSON references (only for OpenAPI versions
                     before 3.0)
  --stand-alone      Whether or not to de-reference JSON schemas
  --kubernetes       Enable Kubernetes specific processors
  --strict           Prohibits properties not in the schema
                     (additionalProperties: false)
  --help             Show this message and exit.
```


## Example

My specific usecase was being able to validate a Kubernetes
configuration file without a Kubernetes client like `kubectl` and
without the server. For that I have a bash script shown below:

```bash
#!/bin/bash -xe

# This script uses openapi2jsonschema to generate a set of JSON schemas
for
# the specified Kubernetes versions in three different flavours:
#
#   X.Y.Z - URL referenced based on the specified GitHub repository
#   X.Y.Z-standalone - de-referenced schemas, more useful as standalone
documents
#   X.Y.Z-local - relative references, useful to avoid the network
dependency

REPO="garethr/kubernetes=json-schema"

declare -a arr=(1.6.6
                1.6.5
                1.6.4
                1.6.3
                1.6.2
                1.6.1
                1.6.0
                1.5.6
                1.5.4
                1.5.3
                1.5.2
                1.5.1
                1.5.0
                )

for version in "${arr[@]}"
do
    schema=https://raw.githubusercontent.com/kubernetes/kubernetes/v${version}/api/openapi-spec/swagger.json
    prefix=https://raw.githubusercontent.com/${REPO}/master/v${version}/_definitions.json

    openapi2jsonschema -o "${version}-standalone" --stand-alone "${schema}"
    openapi2jsonschema -o "${version}-local" "${schema}"
    openapi2jsonschema -o "${version}"" --prefix "${prefix}" "${schema}"
done
```

The output from running this script can be seen in the accompanying
[garethr/kubernetes-json-schema](https://github.com/garethr/kubernetes-json-schema).



