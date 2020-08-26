#!/usr/bin/env python

import json
import re
from copy import deepcopy
from typing import Any, Dict, Optional

import yaml
import urllib
import os
import sys

from jsonref import JsonRef  # type: ignore
import click

from openapi2jsonschema.log import info, debug, error
from openapi2jsonschema.util import (
    additional_properties,
    replace_int_or_string,
    allow_null_optional_fields,
    change_dict_values,
    append_no_duplicates,
)
from openapi2jsonschema.errors import UnsupportedError


@click.command()
@click.option(
    "-o",
    "--output",
    default="schemas",
    metavar="PATH",
    help="Directory to store schema files",
)
@click.option(
    "-p",
    "--prefix",
    default="_definitions.json",
    help="Prefix for JSON references (only for OpenAPI versions before 3.0)",
)
@click.option(
    "-r",
    "--root",
    default=None,
    help="Root class to generate schema for.  Will generate a standalone JSON schema file for this class.",
)
@click.option(
    "--stand-alone", is_flag=True, help="Whether or not to de-reference JSON schemas"
)
@click.option(
    "--expanded", is_flag=True, help="Expand Kubernetes schemas by API version"
)
@click.option(
    "--kubernetes", is_flag=True, help="Enable Kubernetes specific processors"
)
@click.option(
    "--strict",
    is_flag=True,
    help="Prohibits properties not in the schema (additionalProperties: false)",
)
@click.argument("schema", metavar="SCHEMA_URL")
def default(output, schema, prefix, stand_alone, expanded, kubernetes, strict, root: Optional[str]):
    """
    Converts a valid OpenAPI specification into a set of JSON Schema files
    """
    info("Downloading schema")
    if sys.version_info < (3, 0):
        response = urllib.urlopen(schema)
    else:
        if os.path.isfile(schema):
            schema = "file://" + os.path.realpath(schema)
        req = urllib.request.Request(schema)
        response = urllib.request.urlopen(req)

    info("Parsing schema")
    # Note that JSON is valid YAML, so we can use the YAML parser whether
    # the schema is stored in JSON or YAML
    data = yaml.load(response.read(), Loader=yaml.SafeLoader)

    if "swagger" in data:
        version = data["swagger"]
    elif "openapi" in data:
        version = data["openapi"]
    else:
        raise ValueError("Unable to determine OpenAPI version.")

    if not os.path.exists(output):
        os.makedirs(output)

    if version < "3":
        with open("%s/_definitions.json" % output, "w") as definitions_file:
            info("Generating shared definitions")
            definitions = data["definitions"]
            if kubernetes:
                definitions["io.k8s.apimachinery.pkg.util.intstr.IntOrString"] = {
                    "oneOf": [{"type": "string"}, {"type": "integer"}]
                }
                # Although the kubernetes api does not allow `number`  as valid
                # Quantity type - almost all kubenetes tooling
                # recognizes it is valid. For this reason, we extend the API definition to
                # allow `number` values.
                definitions["io.k8s.apimachinery.pkg.api.resource.Quantity"] = {
                    "oneOf": [{"type": "string"}, {"type": "number"}]
                }

                # For Kubernetes, populate `apiVersion` and `kind` properties from `x-kubernetes-group-version-kind`
                for type_name in definitions:
                    type_def = definitions[type_name]
                    if "x-kubernetes-group-version-kind" in type_def:
                        for kube_ext in type_def["x-kubernetes-group-version-kind"]:
                            if expanded and "apiVersion" in type_def["properties"]:
                                api_version = (
                                    kube_ext["group"] + "/" +
                                    kube_ext["version"]
                                    if kube_ext["group"]
                                    else kube_ext["version"]
                                )
                                append_no_duplicates(
                                    type_def["properties"]["apiVersion"],
                                    "enum",
                                    api_version,
                                )
                            if "kind" in type_def["properties"]:
                                kind = kube_ext["kind"]
                                append_no_duplicates(
                                    type_def["properties"]["kind"], "enum", kind
                                )
            if strict:
                definitions = additional_properties(definitions)
            definitions_file.write(json.dumps(
                {"definitions": definitions}, indent=2))

    types = []

    info("Generating individual schemas")
    if version < "3":
        components = data["definitions"]
    else:
        components = data["components"]["schemas"]

    for title in components:
        kind = title.split(".")[-1]  # .lower()
        if kubernetes:
            group = title.split(".")[-3]  # .lower()
            api_version = title.split(".")[-2]  # .lower()
        specification = deepcopy(components[title])
        specification["$schema"] = "http://json-schema.org/schema#"
        specification.setdefault("type", "object")

        if strict:
            specification["additionalProperties"] = False

        if kubernetes and expanded:
            if group in ["core", "api"]:
                full_name = "%s-%s" % (kind, api_version)
            else:
                full_name = "%s-%s-%s" % (kind, group, api_version)
        else:
            full_name = kind

        types.append(title)

        try:
            debug("Processing %s" % full_name)

            # These APIs are all deprecated
            if kubernetes:
                if title.split(".")[3] == "pkg" and title.split(".")[2] == "kubernetes":
                    raise UnsupportedError(
                        "%s not currently supported, due to use of pkg namespace"
                        % title
                    )

            # This list of Kubernetes types carry around jsonschema for Kubernetes and don't
            # currently work with openapi2jsonschema
            if (
                    kubernetes
                    and stand_alone
                    and kind
                    in [
                "jsonschemaprops",
                "jsonschemapropsorarray",
                "customresourcevalidation",
                "customresourcedefinition",
                "customresourcedefinitionspec",
                "customresourcedefinitionlist",
                "customresourcedefinitionspec",
                "jsonschemapropsorstringarray",
                "jsonschemapropsorbool",
            ]
            ):
                raise UnsupportedError("%s not currently supported" % kind)

            updated = change_dict_values(specification, prefix, version)
            specification = updated

            if stand_alone:
                base = "file://%s/%s/" % (os.getcwd(), output)
                specification = JsonRef.replace_refs(
                    specification, base_uri=base)

            if "additionalProperties" in specification:
                if specification["additionalProperties"]:
                    updated = change_dict_values(
                        specification["additionalProperties"], prefix, version
                    )
                    specification["additionalProperties"] = updated

            if strict and "properties" in specification:
                updated = additional_properties(specification["properties"])
                specification["properties"] = updated

            if kubernetes and "properties" in specification:
                updated = replace_int_or_string(specification["properties"])
                updated = allow_null_optional_fields(updated)
                specification["properties"] = updated

            # Normal mode of operation -- generate one JSON schema file per schema
            # defined in the OpenAPI spec.
            if root is None:
                with open("%s/%s.json" % (output, full_name), "w") as schema_file:
                    dbg("Generating %s.json" % full_name)
                    schema_file.write(json.dumps(specification, indent=2))
        except Exception as e:
            error("An error occured processing %s: %s" % (kind, e))

    # unless you are generating a single file for a single JSON schema,
    # then also generate an `all.json` file.
    if root is None:
        with open("%s/all.json" % output, "w") as all_file:
            info("Generating schema for all types")
            contents = {"oneOf": []}
            for title in types:
                if version < "3":
                    contents["oneOf"].append(
                        {"$ref": "%s#/definitions/%s" % (prefix, title)}
                    )
                else:
                    contents["oneOf"].append(
                        {"$ref": (title.replace("#/components/schemas/", "") + ".json")}
                    )
            all_file.write(json.dumps(contents, indent=2))

    else:
        # should fix this naming....
        outfile: str = f"{output}/{root}.json"
        if not components[root]:
            raise ValueError(f"Unable to find JSON class {outfile}")
        contents = components[root]
        contents = rewrite_links(contents)

        info(f"Generating standalone schema for {root} type")
        contents["definitions"] = {}
        contents["$schema"] = "http://json-schema.org/schema#"

        info("Incorporating individual schemas")

        title: str
        spec: Dict[str, Any]
        for title, spec in components.items():
            if title == root:
                continue

            specification: Dict[str, Any] = deepcopy(spec)
            specification.setdefault("type", "object")

            debug(f"Merging schema for {title}:")
            debug(f"{specification}")

            contents["definitions"][title] = rewrite_links(specification)

        with open(outfile, "w") as root_file:
            root_file.write(json.dumps(contents, indent=2))


# Tail-recursive. This is going to be bad. But we can rewrite it later.
def rewrite_links(spec):
    def dict_rewrite(dct):
        new = {}
        for key, value in spec.items():
            if key == "$ref":
                matchval = re.match('.*/([^/]+)$', value)
                if matchval:
                    name: str = matchval.group(1)
                else:
                    raise ValueError(f"Unable to extract a class name from {value}")
                new[key] = "#/definitions/%s" % name
            else:
                new[key] = rewrite_links(value)
        return new

    if isinstance(spec, dict):
        return dict_rewrite(spec)
    elif isinstance(spec, list):
        return [rewrite_links(x) for x in spec]
    else:
        return spec


if __name__ == "__main__":
    default()
