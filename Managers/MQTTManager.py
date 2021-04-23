import os
from time import sleep

import paho.mqtt.client as mqtt
import logging
import json
import sys

from Common.consts import *

_LOGGER = logging.getLogger(__name__)


class MQTTManager:
    def __init__(self, callback):
        self._host = os.getenv("MQTT_BROKER_HOST")
        self._port = int(os.getenv("MQTT_BROKER_PORT"))
        self._username = os.getenv("MQTT_BROKER_USERNAME")
        self._password = os.getenv("MQTT_BROKER_PASSWORD")
        self._client = None
        self.callback = callback

    def connect(self):
        _LOGGER.info("Connecting MQTT Broker")

        try:
            _LOGGER.info(f"Trying connect to MQTT Broker {self._host}:{self._port}")

            self._client = mqtt.Client()
            self._client.user_data_set(self)

            self._client.username_pw_set(self._username, self._password)

            self._client.on_connect = self.on_mqtt_connect
            self._client.on_message = self.on_mqtt_message
            self._client.on_disconnect = self.on_mqtt_disconnect

            self._client.connect(self._host, self._port, 600)
            self._client.loop_start()

            result = True

        except Exception as ex:
            result = False

            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(f"Failed to reconnect, error: {ex}, Line: {exc_tb.tb_lineno}")

        return result

    @staticmethod
    def on_mqtt_connect(client, userdata, flags, rc):

        if rc == 0:
            _LOGGER.info(f"MQTT Broker connected with result code {rc}")

            client.subscribe([
                (TOPIC_STACKS_UPDATE, 0),
                (TOPIC_IMAGES_UPDATE, 0)
            ])

        else:
            error_message = MQTT_ERROR_MESSAGES.get(rc, MQTT_ERROR_DEFAULT_MESSAGE)

            _LOGGER.error(error_message)

    @staticmethod
    def on_mqtt_message(client, userdata, msg):
        payload = None if msg.payload is None else msg.payload.decode("utf-8")

        _LOGGER.info(f"MQTT Message {msg.topic}: {payload}")

        userdata.callback(msg.topic, payload)

    @staticmethod
    def on_mqtt_disconnect(client, userdata, rc):
        _LOGGER.info(f"MQTT Broker disconnected: {rc}")

        userdata.on_disconnect()

    def publish(self, topic, data):
        self._client.publish(topic, json.dumps(data, indent=4))

    def on_disconnect(self):
        connected = False

        while not connected:
            connected = self.connect()

            if not connected:
                _LOGGER.info(f"Next connect attempt in 1 minute")

                sleep(60)
