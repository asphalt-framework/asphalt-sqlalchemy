FROM python:3.5

RUN adduser -u 1000 testuser
RUN wget -qO- https://github.com/jwilder/dockerize/releases/download/v0.3.0/dockerize-linux-amd64-v0.3.0.tar.gz |\
    tar xzC /usr/local/bin
RUN pip install tox
ENTRYPOINT ["dockerize", "-wait", "tcp://postgresql:5432", "-wait", "tcp://mysql:3306",\
            "-timeout", "15s", "tox", "-e", "py35"]
