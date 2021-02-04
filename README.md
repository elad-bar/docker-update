# Portainer2MQTT
Updates all images and performs update stack

## Environment Variables

| Variable | Description | Default |
| ------------- | ------------- | ------------- |
| DOCKER_HOST | Docker connection string | tcp://localhost:2375 |
| PORTAINER_HOST | Portainer host:ip or just hostname | localhost:9000 |
| PORTAINER_SSL | Portainer over SSL | false |
| PORTAINER_USERNAME | Portainer admin username | Empty |
| PORTAINER_PASSWORD | Portainer admin password | Empty |
| MQTT_BROKER_HOST | MQTT Broker host | Empty |
| MQTT_BROKER_PORT | MQTT Broker port | 1883 |
| MQTT_BROKER_USERNAME | MQTT Broker username | Empty |
| MQTT_BROKER_PASSWORD | MQTT Broker password | Empty |
| INTERVAL | Interval between image update check | 01:00:00:00 |

### Interval format
Days:Hours:Minutes:Seconds

## Docker Compose
```
version: '2'
services:
  portainer2mqtt:
    image: "eladbar/portainer2mqtt:latest"
    container_name: "portainer2mqtt"
    hostname: "portainer2mqtt"
    restart: always
    environment:
      - DOCKER_HOST=tcp://localhost:2375
      - PORTAINER_HOST=localhost:9000
      - PORTAINER_SSL=Username
      - PORTAINER_USERNAME=Password
      - PORTAINER_PASSWORD=mqtt-host
      - MQTT_BROKER_HOST=localhost
      - MQTT_BROKER_PORT=1883
      - MQTT_BROKER_USERNAME=Username
      - MQTT_BROKER_PASSWORD=Password 
      - INTERVAL=01:00:00:00
```

## MQTT Messages
### Status update (Publishing)
Topic: ```portainer/containers/status```

Data: 
```json
{
  "containers": {
    "containerName": "Name of the container has an update",
    "imageName": "Image name",
    "imageId": "Current image ID",
    "newImageId": "New image ID"
  }
}
```

### Update stacks (Listening)
Topic: ```portainer/stack/update```

Data: 
```json
{
  "stacks": [ "Name of stacks to update, set null to update all"],
  "autoStopContainers": [ "Name of containers to stop after update"]
}
```

## Changelog

* 2021-Feb-04 - Initial version