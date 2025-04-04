FROM python:alpine

RUN apk add --update ffmpeg

COPY ./requirements/base.txt /code/requirements/base.txt
RUN pip install -Ur /code/requirements/base.txt

COPY . /code/
WORKDIR /code/

CMD ["scripts/entrypoint.sh"]
