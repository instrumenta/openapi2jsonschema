#!/usr/bin/env python

import json
import yaml
import urllib
import os

from jsonref import JsonRef
import click


def replace_int_or_string(data):
    new = {}
    try:
        for k, v in data.iteritems():
            new_v = v
            if isinstance(v, dict):
                if 'format' in v and v['format'] == 'int-or-string':
                    new_v = {'oneOf': [
                        {'type': 'string'},
                        {'type': 'integer'},
                    ]}
                else:
                    new_v = replace_int_or_string(v)
            elif isinstance(v, list):
                new_v = list()
                for x in v:
                    new_v.append(replace_int_or_string(x))
            else:
                new_v = v
            new[k] = new_v
        return new
    except AttributeError:
        return data

def allow_null_arrays(data):
    new = {}
    try:
        for k, v in data.iteritems():
            new_v = v
            if isinstance(v, dict):
                new_v = allow_null_arrays(v)
            elif isinstance(v, list):
                new_v = list()
                for x in v:
                    new_v.append(allow_null_arrays(x))
            elif isinstance(v, basestring):
                if k == "type" and v == "array":
                    new_v = ["array", "null"]
            else:
                new_v = v
            new[k] = new_v
        return new
    except AttributeError:
        return data


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
@click.option('--kubernetes', is_flag=True, help='Enable Kubernetes specific processors')
@click.argument('schema', metavar='SCHEMA_URL')
def default(output, schema, prefix, stand_alone, kubernetes):
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
        definitions = data['definitions']
        if kubernetes:
            definitions['io.k8s.apimachinery.pkg.util.intstr.IntOrString'] = {'oneOf': [
                {'type': 'string'},
                {'type': 'integer'},
            ]}
        definitions_file.write(json.dumps({"definitions": definitions}, indent=2))

    types = []

    info("Generating individual schemas")
    for title in data['definitions']:
        kind = title.split('.')[-1].lower()
        specification = data['definitions'][title]
        specification["$schema"] ="http://json-schema.org/schema#"
        specification["type"] = "object"

        types.append(title)

        if "properties" in specification:
            updated = change_dict_values(specification["properties"], prefix)
            specification["properties"] = updated

        if "additionalProperties" in specification:
            if specification["additionalProperties"]:
                updated = change_dict_values(specification["additionalProperties"], prefix)
                specification["additionalProperties"] = updated

        if stand_alone:
            base = "file://%s/%s/" % (os.getcwd(), output)
            specification = JsonRef.replace_refs(specification, base_uri=base)

        if kubernetes and "properties" in specification:
            updated = replace_int_or_string(specification["properties"])
            updated = allow_null_arrays(updated)
            specification["properties"] = updated

        schema_file_name = "%s.json" % kind
        with open("%s/%s" % (output, schema_file_name), 'w') as schema_file:
            debug("Generating %s" % schema_file_name)
            schema_file.write(json.dumps(specification, indent=2))

    with open("%s/all.json" % output, 'w') as all_file:
        info("Generating schema for all types")
        contents = {"oneOf": []}
        for title in types:
            contents["oneOf"].append({"$ref": "%s#/definitions/%s" % (prefix, title)})
        all_file.write(json.dumps(contents, indent=2))

if __name__ == '__main__':
    default()
