#!/usr/bin/env python

import json
import yaml
import urllib
import os

from jsonref import JsonRef
import click


def change_dict_values(d, prefix):
    new = {}
    for k, v in d.iteritems():
        new_v = v
        if isinstance(v, dict):
            new_v = change_dict_values(v, prefix)
        elif isinstance(v, list):
            new_v = list()
            for x in v:
                new_v.append(change_dict_values(x, prefix))
        elif isinstance(v, basestring):
            if k == "$ref":
                new_v = "%s%s" % (prefix, v)
        else:
            new_v = v
        new[k] = new_v
    return new


def info(message):
    click.echo(click.style(message, fg='green'))

def debug(message):
    click.echo(click.style(message, fg='yellow'))


@click.command()
@click.option('-o', '--output', default='schemas', metavar='PATH', help='Directory to store schema files')
@click.option('-p', '--prefix', default='_definitions.json', help='Prefix for JSON references')
@click.option('--stand-alone', is_flag=True, help='Whether or not to de-reference JSON schemas')
@click.argument('schema', metavar='SCHEMA_URL')
def default(output, schema, prefix, stand_alone):
    """
    Converts a valid OpenAPI specification into a set of JSON Schema files
    """
    info("Downloading schema")
    response = urllib.urlopen(schema)
    info("Parsing schema")
    # Note that JSON is valid YAML, so we can use the YAML parser whether
    # the schema is stored in JSON or YAML
    data = yaml.load(response.read())

    if not os.path.exists(output):
        os.makedirs(output)

    with open("%s/_definitions.json" % output, 'w') as definitions_file:
        info("Generating shared definitions")
        definitions_file.write(json.dumps({"definitions": data['definitions']}, indent=2))

    types = []

    info("Generating individual schemas")
    for title in data['definitions']:
        specification = data['definitions'][title]
        specification["$schema"] ="http://json-schema.org/schema#"
        specification["type"] = "object"

        kind = title.split('.')[-1].lower()
        types.append(title)

        if "properties" in specification:
            updated = change_dict_values(specification["properties"], prefix)
            specification["properties"] = updated

        if "additionalProperties" in specification:
            if specification["additionalProperties"]:
                updated = change_dict_values(specification["additionalProperties"], prefix)
                specification["additionalProperties"] = updated


        schema_file_name = "%s.json" % kind
        with open("%s/%s" % (output, schema_file_name), 'w') as schema_file:
            debug("Generating %s" % schema_file_name)
            if stand_alone:
                base = "file://%s/%s/" % (os.path.dirname(os.path.abspath(__file__)), output)
                schema_file.write(json.dumps(
                    JsonRef.replace_refs(specification, base_uri=base), indent=2))
            else:
                schema_file.write(json.dumps(specification, indent=2))

    with open("%s/all.json" % output, 'w') as all_file:
        info("Generating schema for all types")
        contents = {"oneOf": []}
        for title in types:
            contents["oneOf"].append({"$ref": "%s#/definitions/%s" % (prefix, title)})
        all_file.write(json.dumps(contents, indent=2))

if __name__ == '__main__':
    default()
