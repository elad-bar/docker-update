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

TOPIC_IMAGES_STATUS = "portainer/images/pending"
TOPIC_IMAGES_UPDATE = "portainer/images/update"
TOPIC_STACKS_UPDATE = "portainer/stacks/update"

STATUS_IDLE = "Idle"
STATUS_UPDATING_IMAGES = "Updating images"
STATUS_UPDATING_STACK = "Updating stacks"
STATUS_STOPPING_CONTAINERS = "Stopping containers"
