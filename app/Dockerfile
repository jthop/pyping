FROM python:3.10.0b1-buster
#FROM python:3.7.3-slim
#FROM python:3.7.3-alpine22x

#RUN apt-get update && apt-get install -y monitoring-plugins-basic

RUN pip3 install --upgrade pip
COPY requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt

COPY . /app
WORKDIR /app

ENV INSIDE_CONTAINER Yes

CMD ["gunicorn"  , "--bind", "0.0.0.0:80", "main:app"]

