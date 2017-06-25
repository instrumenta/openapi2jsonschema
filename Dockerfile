FROM python:2-alpine

RUN pip install openapi2jsonschema

ENTRYPOINT ["/usr/local/bin/openapi2jsonschema"]
CMD ["--help"]

