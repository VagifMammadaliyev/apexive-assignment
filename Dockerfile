FROM python:3.8.5

ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    gettext \
    libmagic1

WORKDIR /code
COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY app /code

CMD ["uwsgi", "--ini", "uwsgi.ini", "--listen", "10000"]
