FROM python:3.9-buster
#FROM python:3.7.3-slim
#FROM python:3.7.3-alpine

RUN pip3 install --upgrade pip
COPY requirements.txt /
RUN pip3 install -r /requirements.txt

COPY . /app
WORKDIR /app

ENV INSIDE_CONTAINER Yes

CMD ["gunicorn"  , "--bind", "0.0.0.0:6768", "main:app"]

