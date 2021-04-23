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

MQTT_ERROR_DEFAULT_MESSAGE = "Unknown error"

MQTT_ERROR_MESSAGES = {
    1: "MQTT Broker failed to connect: incorrect protocol version",
    2: "MQTT Broker failed to connect: invalid client identifier",
    3: "MQTT Broker failed to connect: server unavailable",
    4: "MQTT Broker failed to connect: bad username or password",
    5: "MQTT Broker failed to connect: not authorised"
}
