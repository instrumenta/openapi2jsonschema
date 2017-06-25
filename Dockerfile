FROM python:2-alpine
MAINTAINER Gareth Rushgrove "gareth@morethanseven.net"

RUN pip install openapi2jsonschema

ENTRYPOINT ["/usr/local/bin/openapi2jsonschema"]
CMD ["--help"]
