FROM python:2-alpine
MAINTAINER Gareth Rushgrove "gareth@morethanseven.net"

COPY . /src
RUN cd src && pip install -e .

WORKDIR /out

ENTRYPOINT ["/usr/local/bin/openapi2jsonschema"]
CMD ["--help"]
