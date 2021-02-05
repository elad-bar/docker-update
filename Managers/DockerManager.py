import sys
import os
import json
from typing import List

import aiohttp
import docker
import logging

from aiohttp import ClientSession

from Common.consts import *

_LOGGER = logging.getLogger(__name__)


class DockerManager:
    def __init__(self):
        _LOGGER.info("Loading configuration")

        self._client = docker.from_env()
        self._portainer_host = os.getenv("PORTAINER_HOST")
        self._portainer_ssl = os.getenv("PORTAINER_SSL", False).lower() == str(True).lower()
        self._portainer_username = os.getenv("PORTAINER_USERNAME")
        self._portainer_password = os.getenv("PORTAINER_PASSWORD")
        self._status = STATUS_IDLE

        _LOGGER.info((
            f"Loading configuration for {self._portainer_username}:{self._portainer_password}@{self._portainer_host}"
            f" - SSL: {self._portainer_ssl}"
        ))

        self._ssl_context = False if self._portainer_ssl else None
        self._headers = None

    @property
    def status(self):
        return self._status

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

    def reset_status(self):
        self._status = STATUS_IDLE

    def validate_status(self, to_status):
        is_idle = self._status == STATUS_IDLE

        if is_idle:
            self._status = to_status
        else:
            _LOGGER.warning(f"Cannot perform action while {self._status}")

        return is_idle

    async def login(self, session: ClientSession):
        login_data = {
            "Username": self._portainer_username,
            "Password": self._portainer_password
        }

        _LOGGER.info("Login Portainer")
        async with session.post(self.auth_url, data=json.dumps(login_data)) as resp:
            resp.raise_for_status()

            json_response = await resp.json()
            jwt_token = json_response.get("jwt")

        self._headers = {
            "Authorization": f"Bearer {jwt_token}"
        }

    async def get_stacks(self, session: ClientSession):
        _LOGGER.info("Get stacks from Portainer")
        async with session.get(self.stacks_url, headers=self._headers) as resp:
            resp.raise_for_status()

            stacks = await resp.json()

        return stacks

    async def get_stack_content(self, session: ClientSession, stack_id, name):
        _LOGGER.info(f"Get stack {name} [#{stack_id}]")
        url = f"{self.stacks_url}/{stack_id}/file"

        async with session.get(url, headers=self._headers) as resp:
            resp.raise_for_status()

            update_stack_data = await resp.json()

            return update_stack_data

    async def update_stack(self, session: ClientSession, stack_id, name, content):
        _LOGGER.info(f"Redeploy stack {name} [#{stack_id}]")
        url = f"{self.stacks_url}/{stack_id}?endpointId=1"

        async with session.put(url, headers=self._headers, data=json.dumps(content)) as resp:
            resp.raise_for_status()

    async def update_stacks(self, session: ClientSession, stacks, include_stacks: List[str] = None):
        for stack in stacks:
            stack_id = stack.get("Id")
            stack_name = stack.get("Name")

            if include_stacks is None or stack_name in include_stacks:
                content = await self.get_stack_content(session, stack_id, stack_name)

                await self.update_stack(session, stack_id, stack_name, content)

            else:
                _LOGGER.info(f"Skip stack {stack_name} [#{stack_id}]")

    async def update_stacks_async(self, include_stacks: List[str] = None):
        if not self.validate_status(STATUS_UPDATING_STACK):
            return

        try:
            connector = aiohttp.TCPConnector(ssl=self._ssl_context)

            async with ClientSession(connector=connector) as session:
                await self.login(session)

                stacks = await self.get_stacks(session)

                await self.update_stacks(session, stacks, include_stacks)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(f"Failed to reconnect, error: {ex}, Line: {exc_tb.tb_lineno}")

        self.reset_status()

    def auto_stop_containers(self, containers: List[str]):
        if not self.validate_status(STATUS_STOPPING_CONTAINERS):
            return

        for container_name in containers:
            _LOGGER.info(f"Stopping container: {container_name}")

            container = self._client.containers.get(container_name)
            container.stop()

        self.reset_status()

    async def update_images_async(self, publish):
        if not self.validate_status(STATUS_UPDATING_IMAGES):
            return

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

            publish(TOPIC_IMAGES_STATUS, message)

        self.reset_status()
