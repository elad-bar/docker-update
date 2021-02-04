FROM python:3.9-alpine

ENV PORTAINER_HOST ""
ENV PORTAINER_SSL false
ENV PORTAINER_USERNAME ""
ENV PORTAINER_PASSWORD ""
ENV MQTT_BROKER_HOST ""
ENV MQTT_BROKER_PORT 1883
ENV MQTT_BROKER_USERNAME ""
ENV MQTT_BROKER_PASSWORD ""
ENV INTERVAL "01:00:00:00"
ENV DEBUG false
ENV DOCKER_HOST "tcp://localhost:2375"

RUN apk update && \
    apk upgrade && \
    apk add --no-cache gcc libressl-dev musl-dev libffi-dev nano && \
    pip install aiohttp paho-mqtt docker

COPY . /app/

ENTRYPOINT ["python3", "/app/entrypoint.py"]