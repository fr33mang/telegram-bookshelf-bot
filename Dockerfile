FROM python:3.7-alpine
RUN apk add --update --no-cache g++ libressl-dev postgresql-dev libffi-dev gcc musl-dev python3-dev libxml2-dev libxslt-dev
WORKDIR /code
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]