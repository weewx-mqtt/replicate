---
title: Responder
parent: Configuring MQTTReplicate
nav_order: 2
---

## `[[Responder]]`

Configuration data for the responder (the WeeWX service).

### enable = false

### host

The MQTT server.
The default value is localhost.

### port

The port to connect to.
The default value is 1883.

### keepalive

Maximum period in seconds allowed between communications with the broker.
The default is 60.

### log_mqtt

Controls the MQTT logging.
Valid values are `true` or `false`.
The default value is false.

### subscribe_qos

The MQTT QOS when subscribing to a topic.
The default value is 1.

### publish_qos

The MQTT QOS when publishing to a topic.
The default value is 1.

### archive_topic

The topic that the replication data is published to.
And therefore the topic that is subscribed to receive it.
The default value is replicate/archive.

### request_topic

The prefix for the request topic.
Each replicating instance will have a unique request_topic
The default value is replicate/request.
The final default value is 'replicate/request/{instance name}'
The request topic is the topic that the requester uses to request 'catchup'/'backfill' data.
So, the responser subscribes to this topic

### delta

When retrieving secondary data to be published, replicated the largest difference in time that is accepted.
Some extensions do not force the time to an archive interval, so the WeeWX default value of 'None' does not always work.
The default value is 60.

### max_responder_threads

The maximum number of responser threads to create.
The default value is 1.
DEPRECATED - DO NOT USE
