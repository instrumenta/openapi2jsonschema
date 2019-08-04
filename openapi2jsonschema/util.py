#!/usr/bin/env python


def iteritems(d):
    if hasattr(dict, "iteritems"):
        return d.iteritems()
    else:
        return iter(d.items())


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
                if "format" in v and v["format"] == "int-or-string":
                    new_v = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
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
                is_non_null_type = k == "type" and v != "null"
                has_required_fields = grand_parent and "required" in grand_parent
                is_required_field = (
                    has_required_fields and key in grand_parent["required"]
                )
                if is_non_null_type and not is_required_field:
                    new_v = [v, "null"]
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
                    if version < "3":
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
