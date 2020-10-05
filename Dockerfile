FROM python:3.8-slim as build
WORKDIR /code

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY . .

FROM build as dev_build

RUN pip install -r requirements.dev.txt
