---
title: Requester
parent: Configuring MQTTReplicate
nav_order: 1
---

## `[[Requester]]`

Configuration data for the requester (the WeeWX driver).

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

### response_topic

The prefix for response topic.
The default value is replicate/response.
The final default value is 'replicate/response/{MQTT client id}'.
The response topic is the topic that the responser publishes 'catchup'/'backfill' data to.
And therefore the response topic is the topic that the requester subscribes to.

### loop_interval

The time between between generating loop packets.
The default value is 2.5.

### archive_interval

The WeeWX archive interval.
The default value is 300.

### startup_max_tries

When performing 'catch up', the maximum number of times to see if the necessary data is available.
The default value is 2.

### startup_wait_before_retry

When performing 'catch up', the amount of time to `wait` for the necessary data.
The default value is 10.

### archive_max_tries

When generating archive records, the maximum number of times to see if the necessary data is available.
The default value is 2.
