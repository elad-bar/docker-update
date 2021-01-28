import sys
import os
import json
import asyncio
import aiohttp
import docker
import logging

PROTOCOLS = {
    True: "https",
    False: "http"
}

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

        containers_to_stop = os.getenv("CONTAINERS_TO_STOP", "")

        self._client = docker.from_env()
        self._portainer_host = os.getenv("PORTAINER_HOST")
        self._portainer_ssl = bool(os.getenv("PORTAINER_SSL", False))
        self._portainer_username = os.getenv("PORTAINER_USERNAME")
        self._portainer_password = os.getenv("PORTAINER_PASSWORD")
        self._portainer_stack_id = os.getenv("PORTAINER_STACK_ID")
        self._containers_to_stop = containers_to_stop.split(",")

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
    def stack_url(self):
        return f"{self.base_url}/api/stacks/{self._portainer_stack_id}"

    @property
    def stack_file_url(self):
        return f"{self.stack_url}/file"

    async def update(self):
        _LOGGER.info("Starting to update")

        downloaded_images = self.update_docker()

        if len(downloaded_images) > 0 and self._portainer_host is not None:
            await self.reload_containers()

            self.stop_relevant_containers()

        _LOGGER.info("Updated completed")

    async def reload_containers(self):
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

            _LOGGER.info("Get stack file content from Portainer")
            async with session.get(self.stack_file_url, headers=headers) as resp:
                resp.raise_for_status()

                json_response = await resp.json()
                stack_file_content = json_response.get("StackFileContent")

            update_stack_data = {
                "StackFileContent": stack_file_content
            }

            if not self._is_debug:
                _LOGGER.info("Redeploy stack via Portainer")
                url = f"{self.stack_url}?endpointId=1"

                async with session.put(url, headers=headers, data=json.dumps(update_stack_data)) as resp:
                    resp.raise_for_status()
            else:
                _LOGGER.info("Skipping redeploy stack via Portainer")

    def stop_relevant_containers(self):
        for container_name in self._containers_to_stop:
            _LOGGER.info(f"Stopping container: {container_name}")

            container = self._client.containers.get(container_name)
            container.stop()

    def update_docker(self):
        containers = self._client.containers.list()
        downloaded = []

        _LOGGER.info("Starting to look for new images")

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
                _LOGGER.info(f"{name}: {image_name} - Image pulled")
                downloaded.append(name)

        return downloaded


manager = Manager()

loop = asyncio.get_event_loop()
loop.run_until_complete(manager.update())
loop.close()