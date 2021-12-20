FROM python:3.7

RUN wget -qO- https://github.com/jwilder/dockerize/releases/download/v0.6.1/dockerize-linux-amd64-v0.6.1.tar.gz |\
    tar xzC /usr/local/bin

ENV SETUPTOOLS_SCM_PRETEND_VERSION 2.0.0

WORKDIR /app
COPY src ./src
COPY setup.* pyproject.toml README.rst ./
RUN pip install -e .[test]
