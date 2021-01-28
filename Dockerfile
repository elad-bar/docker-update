FROM python:3.9-alpine

ENV CONTAINERS_TO_STOP ""
ENV PORTAINER_HOST ""
ENV PORTAINER_SSL false
ENV PORTAINER_USERNAME ""
ENV PORTAINER_PASSWORD ""
ENV PORTAINER_STACK_ID 1
ENV DEBUG false

RUN apk update && \
    apk upgrade && \
    apk add --no-cache gcc libressl-dev musl-dev libffi-dev nano && \
    pip install aiohttp && \
    pip install docker

COPY . /app/

ENTRYPOINT ["python3", "/app/entrypoint.py"]