import sys
import os
import json
import asyncio
from time import sleep
from typing import List

import aiohttp
import docker
import logging
import paho.mqtt.client as mqtt

PROTOCOLS = {
    True: "https",
    False: "http"
}

INTERVAL_MAPPING = {
    "0": 24 * 60 * 60,
    "1": 60 * 60,
    "2": 60,
    "3": 1
}

DEFAULT_INTERVAL = "01:00:00:00"

TOPIC_STATUS = "portainer/containers/status"
TOPIC_UPDATE = "portainer/stack/update"

root = logging.getLogger()
root.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s', datefmt='%b %d %Y %H:%M:%S')
handler.setFormatter(formatter)
root.addHandler(handler)

_LOGGER = logging.getLogger(__name__)


class Manager:
    def __init__(self):
        _LOGGER.info("Loading configuration")

        self._loop = asyncio.get_event_loop()

        self._client = docker.from_env()
        self._portainer_host = os.getenv("PORTAINER_HOST")
        self._portainer_ssl = bool(os.getenv("PORTAINER_SSL", False))
        self._portainer_username = os.getenv("PORTAINER_USERNAME")
        self._portainer_password = os.getenv("PORTAINER_PASSWORD")

        self._mqtt_broker_host = os.getenv("MQTT_BROKER_HOST")
        self._mqtt_broker_port = os.getenv("MQTT_BROKER_PORT")
        self._mqtt_broker_username = os.getenv("MQTT_BROKER_USERNAME")
        self._mqtt_broker_password = os.getenv("MQTT_BROKER_PASSWORD")

        interval = os.getenv("INTERVAL", DEFAULT_INTERVAL)
        interval_seconds = 0
        interval_parts = interval.split(":")

        if len(interval_parts) != 4:
            _LOGGER.warning("Invalid interval, setting to default")

            interval = DEFAULT_INTERVAL

        index = 0
        for i in interval_parts:
            maximum = 60

            if index == 0:
                maximum = None

            if maximum is not None and int(i) > maximum:
                _LOGGER.warning(f"Invalid interval, expected up to {maximum}, actual: {i}, setting to default")

                interval = DEFAULT_INTERVAL

            if int(i) < 0:
                _LOGGER.warning(f"Invalid interval, {i} is below minimum, setting to default")

                interval = DEFAULT_INTERVAL

            index += 1

        interval_parts = interval.split(":")

        index = 0
        for i in interval_parts:
            factor = INTERVAL_MAPPING.get(str(index))

            interval_seconds += factor * int(i)

            index += 1

        self._interval = interval_seconds

        self._mqtt_client = mqtt.Client()

        _LOGGER.info((
            f"Loading configuration for {self._portainer_username}:{self._portainer_password}@{self._portainer_host}"
            f" - SSL: {self._portainer_ssl}"
        ))

        ssl_context = False if self._portainer_ssl else None
        self._connector = aiohttp.TCPConnector(ssl=ssl_context)

        self._is_debug = os.getenv("DEBUG", False)

    @property
    def base_url(self):
        protocol = PROTOCOLS[self._portainer_ssl]

        return f"{protocol}://{self._portainer_host}"

    @property
    def auth_url(self):
        return f"{self.base_url}/api/auth"

    @property
    def stacks_url(self):
        return f"{self.base_url}/api/stacks"

    def initialize(self):
        self.initialize_mqtt_client()

        _LOGGER.info(self._interval)

        while True:
            try:
                self._loop.run_until_complete(self.update_images())

                _LOGGER.info(f"Next iteration in {self._interval} seconds")
                sleep(self._interval)

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                line = exc_tb.tb_lineno

                _LOGGER.error(f"Connection failed will try to connect in 30 seconds, error: {ex}, Line: {line}")

                sleep(30)

    def initialize_mqtt_client(self):
        _LOGGER.info("Connecting MQTT Broker")

        self._mqtt_client.username_pw_set(self._mqtt_broker_username, self._mqtt_broker_password)

        self._mqtt_client.on_connect = self.on_mqtt_connect
        self._mqtt_client.on_message = self.on_mqtt_message
        self._mqtt_client.on_disconnect = self.on_mqtt_disconnect

        self._mqtt_client.connect(self._mqtt_broker_host, int(self._mqtt_broker_port), 600)
        self._mqtt_client.loop_start()

    @staticmethod
    def on_mqtt_connect(client, userdata, flags, rc):
        _LOGGER.info(f"MQTT Broker connected with result code {rc}")

        client.subscribe(TOPIC_UPDATE)

    @staticmethod
    def on_mqtt_message(client, userdata, msg):
        _LOGGER.debug(f"MQTT Message {msg.topic}: {msg.payload}")

        if msg.topic == TOPIC_UPDATE:
            payload = msg.payload.decode("utf-8")

            data = {}

            if len(payload) > 0:
                data = json.loads(payload)

            stacks = data.get("stacks")
            auto_stop_containers = data.get("autoStopContainers", [])

            _LOGGER.info(f"Stacks: {stacks}")
            _LOGGER.info(f"Auto Stop Containers: {auto_stop_containers}")

            manager.update(stacks, auto_stop_containers)

    @staticmethod
    def on_mqtt_disconnect(client, userdata, rc):
        connected = False

        while not connected:
            try:
                _LOGGER.info(f"MQTT Broker got disconnected trying to reconnect")

                mqtt_broker_host = os.getenv('MQTT_BROKER_HOST')
                mqtt_broker_port = os.getenv('MQTT_BROKER_PORT')

                client.connect(mqtt_broker_host, int(mqtt_broker_port), 600)
                client.loop_start()

                connected = True

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()

                _LOGGER.error(f"Failed to reconnect, retry in 60 seconds, error: {ex}, Line: {exc_tb.tb_lineno}")

                sleep(60)

    def update(self, include_stacks: List[str] = None, auto_stop_containers: List[str] = None):
        _LOGGER.info("Starting to update")

        self._loop.run_until_complete(self.reload_containers(include_stacks))

        self.stop_relevant_containers(auto_stop_containers)

        _LOGGER.info("Updated completed")

    def reload_containers_sync(self, include_stacks: List[str]):
        self._loop.run_until_complete(self.reload_containers(include_stacks))

    async def reload_containers(self, include_stacks: List[str] = None):
        async with aiohttp.ClientSession(connector=self._connector) as session:
            login_data = {
                "Username": self._portainer_username,
                "Password": self._portainer_password
            }

            _LOGGER.info("Login Portainer")
            async with session.post(self.auth_url, data=json.dumps(login_data)) as resp:
                resp.raise_for_status()

                json_response = await resp.json()
                jwt_token = json_response.get("jwt")

            headers = {
                "Authorization": f"Bearer {jwt_token}"
            }

            _LOGGER.info("Get stacks from Portainer")
            async with session.get(self.stacks_url, headers=headers) as resp:
                resp.raise_for_status()

                stacks = await resp.json()

            for stack in stacks:
                stack_id = stack.get("Id")
                stack_name = stack.get("Name")

                stack_url = f"{self.stacks_url}/{stack_id}"
                stack_file_url = f"{stack_url}/file"

                if include_stacks is None or stack_name in include_stacks:
                    _LOGGER.info(f"Get stack {stack_name} [#{stack_id}]")
                    async with session.get(stack_file_url, headers=headers) as resp:
                        resp.raise_for_status()

                        update_stack_data = await resp.json()

                    url = f"{stack_url}?endpointId=1"

                    _LOGGER.info(f"Redeploy stack {stack_name} [#{stack_id}]")
                    async with session.put(url, headers=headers, data=json.dumps(update_stack_data)) as resp:
                        resp.raise_for_status()

                else:
                    _LOGGER.info(f"Skip stack {stack_name} [#{stack_id}]")

    def stop_relevant_containers(self, auto_stop_containers: List[str]):
        for container_name in auto_stop_containers:
            _LOGGER.info(f"Stopping container: {container_name}")

            container = self._client.containers.get(container_name)
            container.stop()

    async def update_images(self):
        _LOGGER.info("Starting to look for new images")

        containers = self._client.containers.list()

        containers_data = []

        index = 0
        total = len(containers)

        for item in containers:
            index += 1

            image_id = item.attrs.get("Image")
            name = item.attrs.get("Name")[1:]
            config = item.attrs.get("Config")
            image_name = config.get("Image")

            if ":" not in image_name:
                image_name = f"{image_name}:latest"

            _LOGGER.info(f"{index:03}/{total:03}\t{name}: {image_name}")

            new_image = self._client.images.pull(image_name)

            new_image_id = new_image.attrs.get("Id")

            if new_image_id != image_id:
                container_data = {
                    "containerName": name,
                    "imageName": image_name,
                    "imageId": image_id,
                    "newImageId": new_image_id
                }

                containers_data.append(container_data)

                _LOGGER.info(f"{name}: {image_name} - Image pulled")

        updated = len(containers_data) > 0

        if updated:
            message = {
                "containers": containers_data
            }

            self._mqtt_client.publish(TOPIC_STATUS, json.dumps(message, indent=4))


manager = Manager()

manager.initialize()
