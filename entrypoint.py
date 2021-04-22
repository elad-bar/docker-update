import sys
import os
import json
import asyncio
from time import sleep
from typing import List

import logging

from Common.consts import *
from Managers.DockerManager import DockerManager
from Managers.MQTTManager import MQTTManager

log_level = logging.INFO
is_debug = os.getenv("DEBUG", False).lower() == str(True).lower()

if is_debug:
    log_level = logging.DEBUG

root = logging.getLogger()
root.setLevel(log_level)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(log_level)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s', datefmt='%b %d %Y %H:%M:%S')
handler.setFormatter(formatter)
root.addHandler(handler)

_LOGGER = logging.getLogger(__name__)


class Manager:
    def __init__(self):
        _LOGGER.info("Loading configuration")

        self._loop = asyncio.get_event_loop()

        self._docker_manager: DockerManager = DockerManager()
        self._mqtt_manager: MQTTManager = MQTTManager(self.mqtt_manager_callback)

        self._interval = self.interval

        self._docker_manager.get_ha()

    @property
    def interval(self):
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

        return interval_seconds

    def initialize(self):
        self._mqtt_manager.connect()

        while True:
            try:
                self.update_images()

                _LOGGER.info(f"Next iteration in {self._interval} seconds")
                sleep(self._interval)

            except Exception as ex:
                self._docker_manager.reset_status()
                
                exc_type, exc_obj, exc_tb = sys.exc_info()
                line = exc_tb.tb_lineno

                _LOGGER.error(f"Connection failed will try to connect in 30 seconds, error: {ex}, Line: {line}")

                sleep(30)

    def mqtt_manager_callback(self, topic, payload):
        if topic == TOPIC_STACKS_UPDATE:
            data = {}

            if len(payload) > 0:
                data = json.loads(payload)

            stacks = data.get("stacks")
            auto_stop_containers = data.get("autoStopContainers", [])

            stacks_description = "all" if stacks is None else ", ".join(stacks)
            stop_containers_description = "none" if auto_stop_containers is None else ", ".join(auto_stop_containers)

            _LOGGER.info(f"Stacks: {stacks_description}")
            _LOGGER.info(f"Auto Stop Containers: {stop_containers_description}")

            self.update_stacks(stacks, auto_stop_containers)
        elif topic == TOPIC_IMAGES_UPDATE:
            self.update_images()

    def update_stacks(self, include_stacks: List[str] = None, stop_containers: List[str] = None):
        _LOGGER.info("Starting to update stacks")

        self._loop.run_until_complete(self._docker_manager.update_stacks_async(include_stacks))

        self._docker_manager.auto_stop_containers(stop_containers)

        _LOGGER.info("Update stacks completed")

    def update_images(self):
        publish = self._mqtt_manager.publish
        update_images_async = self._docker_manager.update_images_async

        self._loop.run_until_complete(update_images_async(publish))


manager = Manager()

# manager.initialize()
