#!/usr/bin/env python

import json
import yaml
import urllib
import os
import sys

from jsonref import JsonRef
import click


class UnsupportedError(Exception):
    pass


try:
    dict.iteritems
except AttributeError:
    # Python 3
    def iteritems(d):
        return iter(d.items())
else:
    # Python 2
    def iteritems(d):
        return d.iteritems()


def additional_properties(data):
    "This recreates the behaviour of kubectl at https://github.com/kubernetes/kubernetes/blob/225b9119d6a8f03fcbe3cc3d590c261965d928d0/pkg/kubectl/validation/schema.go#L312"
    new = {}
    try:
        for k, v in iteritems(data):
            new_v = v
            if isinstance(v, dict):
                if "properties" in v:
                    if "additionalProperties" not in v:
                        v["additionalProperties"] = False
                new_v = additional_properties(v)
            else:
                new_v = v
            new[k] = new_v
        return new
    except AttributeError:
        return data


def replace_int_or_string(data):
    new = {}
    try:
        for k, v in iteritems(data):
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


def allow_null_optional_fields(data, parent=None, grand_parent=None, key=None):
    new = {}
    try:
        for k, v in iteritems(data):
            new_v = v
            if isinstance(v, dict):
                new_v = allow_null_optional_fields(v, data, parent, k)
            elif isinstance(v, list):
                new_v = list()
                for x in v:
                    new_v.append(allow_null_optional_fields(x, v, parent, k))
            elif isinstance(v, str):
                is_array = k == "type" and v == "array"
                is_string = k == "type" and v == "string"
                has_required_fields = grand_parent and "required" in grand_parent
                is_required_field = has_required_fields and key in grand_parent["required"]
                if is_array and not is_required_field:
                    new_v = ["array", "null"]
                elif is_string and not is_required_field:
                    new_v = ["string", "null"]
            new[k] = new_v
        return new
    except AttributeError:
        return data


def change_dict_values(d, prefix, version):
    new = {}
    try:
        for k, v in iteritems(d):
            new_v = v
            if isinstance(v, dict):
                new_v = change_dict_values(v, prefix, version)
            elif isinstance(v, list):
                new_v = list()
                for x in v:
                    new_v.append(change_dict_values(x, prefix, version))
            elif isinstance(v, str):
                if k == "$ref":
                    if version < '3':
                        new_v = "%s%s" % (prefix, v)
                    else:
                        new_v = v.replace("#/components/schemas/", "") + ".json"
            else:
                new_v = v
            new[k] = new_v
        return new
    except AttributeError:
        return d

def append_no_duplicates(obj, key, value):
    """
    Given a dictionary, lookup the given key, if it doesn't exist create a new array.
    Then check if the given value already exists in the array, if it doesn't add it.
    """
    if key not in obj:
        obj[key] = []
    if value not in obj[key]:
        obj[key].append(value)


def info(message):
    click.echo(click.style(message, fg='green'))


def debug(message):
    click.echo(click.style(message, fg='yellow'))


def error(message):
    click.echo(click.style(message, fg='red'))


@click.command()
@click.option('-o', '--output', default='schemas', metavar='PATH', help='Directory to store schema files')
@click.option('-p', '--prefix', default='_definitions.json', help='Prefix for JSON references (only for OpenAPI versions before 3.0)')
@click.option('--stand-alone', is_flag=True, help='Whether or not to de-reference JSON schemas')
@click.option('--expanded', is_flag=True, help='Expand Kubernetes schemas by API version')
@click.option('--kubernetes', is_flag=True, help='Enable Kubernetes specific processors')
@click.option('--strict', is_flag=True, help='Prohibits properties not in the schema (additionalProperties: false)')
@click.argument('schema', metavar='SCHEMA_URL')
def default(output, schema, prefix, stand_alone, expanded, kubernetes, strict):
    """
    Converts a valid OpenAPI specification into a set of JSON Schema files
    """
    info("Downloading schema")
    if sys.version_info < (3, 0):

        response = urllib.urlopen(schema)
    else:
        if os.path.isfile(schema):
            schema = 'file://' + os.path.realpath(schema)
        req = urllib.request.Request(schema)
        response = urllib.request.urlopen(req)

    info("Parsing schema")
    # Note that JSON is valid YAML, so we can use the YAML parser whether
    # the schema is stored in JSON or YAML
    data = yaml.load(response.read(), Loader=yaml.SafeLoader)

    if 'swagger' in data:
        version = data['swagger']
    elif 'openapi' in data:
        version = data['openapi']

    if not os.path.exists(output):
        os.makedirs(output)

    if version < '3':
        with open("%s/_definitions.json" % output, 'w') as definitions_file:
            info("Generating shared definitions")
            definitions = data['definitions']
            if kubernetes:
                definitions['io.k8s.apimachinery.pkg.util.intstr.IntOrString'] = {'oneOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ]}
                definitions['io.k8s.apimachinery.pkg.api.resource.Quantity'] = {'oneOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ]}
            if strict:
                definitions = additional_properties(definitions)
            definitions_file.write(json.dumps({"definitions": definitions}, indent=2))

    types = []

    info("Generating individual schemas")
    if version < '3':
        components = data['definitions']
    else:
        components = data['components']['schemas']

    for title in components:
        kind = title.split('.')[-1].lower()
        if kubernetes:
          group = title.split('.')[-3].lower()
          api_version = title.split('.')[-2].lower()
        specification = components[title]
        specification["$schema"] = "http://json-schema.org/schema#"
        specification.setdefault("type", "object")

        if kubernetes and expanded:
            if group == "api":
                full_name = "%s-%s" % (kind, api_version)
            else:
                full_name = "%s-%s-%s" % (kind, group, api_version)
        else:
          full_name = kind

        types.append(title)

        try:
            debug("Processing %s" % full_name)

            updated = change_dict_values(specification, prefix, version)
            specification = updated

            # This list of Kubernetes types carry around jsonschema for Kubernetes and don't
            # currently work with openapi2jsonschema
            if kubernetes and stand_alone and kind in ["jsonschemaprops", "jsonschemapropsorarray", "customresourcevalidation", "customresourcedefinition", "customresourcedefinitionspec", "customresourcedefinitionlist", "customresourcedefinitionspec", "jsonschemapropsorstringarray", "jsonschemapropsorbool"]:
                raise UnsupportedError("%s not currently supported" % kind)

            if stand_alone:
                base = "file://%s/%s/" % (os.getcwd(), output)
                specification = JsonRef.replace_refs(specification, base_uri=base)

            if "additionalProperties" in specification:
                if specification["additionalProperties"]:
                    updated = change_dict_values(specification["additionalProperties"], prefix, version)
                    specification["additionalProperties"] = updated

            if strict and "properties" in specification:
                updated = additional_properties(specification["properties"])
                specification["properties"] = updated

            if kubernetes and "properties" in specification:
                updated = replace_int_or_string(specification["properties"])
                updated = allow_null_optional_fields(updated)
                specification["properties"] = updated

            with open("%s/%s.json" % (output, full_name), 'w') as schema_file:
                debug("Generating %s.json" % full_name)
                schema_file.write(json.dumps(specification, indent=2))
        except Exception as e:
            error("An error occured processing %s: %s" % (kind, e))

    with open("%s/all.json" % output, 'w') as all_file:
        info("Generating schema for all types")
        contents = {"oneOf": []}
        for title in types:
            if version < '3':
                contents["oneOf"].append({"$ref": "%s#/definitions/%s" % (prefix, title)})
            else:
                contents["oneOf"].append({"$ref": (title.replace("#/components/schemas/", "") + ".json")})
        all_file.write(json.dumps(contents, indent=2))


if __name__ == '__main__':
    default()
