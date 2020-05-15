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
without the server. For that I have a bash script,
[available here](https://github.com/instrumenta/kubernetes-json-schema/blob/master/build.sh).

The output from running this script can be seen in the accompanying
[instrumenta/kubernetes-json-schema](https://github.com/instrumenta/kubernetes-json-schema).

