---
title: Home Page
has_children: true
has_toc: true
nav_order: 1
nav_exclude: true
---

Using MQTT V5 request/respond functionality, replicate WeeWX database(s).
The requester, a WeeWX driver, is the secondary (copy) database(s).
The responder, a WeeWX service, is the primary database(s).

## Requester

### Top-level thread

#### When instance is created

- Thread is created to process data from responder (primary database(s)).
- Publishes a request for all records later than last record in database(s).
  - topic: replicate/request/instance-name
  - ResponseTopic property: replicate/response/clientid
  - UserProperty property: data_binding = instance-name/responder-binding-name
  - Note: 'main' binding request is done last
- Note: The response will be processed in the secondary thread.

#### genStartupRecords

- Processes 'main' binding data queue.

#### genArchiveRecords

- Processes the 'main' binding data queue.

#### genLoopPackets

- Generates 'empty' packets
  - Required for WeeWX processing.

### Child thread

- Connects using paho mqtt client that is shared with primary thread.
- Subscribes to 'catchup' topic to receive 'catchup' data.
  - topic: replicate/request/instance-name
- Subscribes to 'archive' topic to receive 'archive' data.
  - topic: replicate/archive
- Runs paho mqtt in 'blocking mode' (loop_forever)
- When MQTT message is received
  - For 'main' database, data put into the queue to be processed by the primary thread (genStartupRecords or genArchiveRecords).
  - For other databases, database is updated directly.

## Responder

Consists of 3 threads

### Top-level thread

thread creation

- All paho mqtt callbacks are handled in the secondary thread.
- When new_archive_record is raised, publishes archive data for all databases.
  - topic: replicate/archive
  - UserProperty property: data_binding=instance-name/responder-binding-name
  - Note: 'main' binding published last
  - Note: 'main' binding uses the archive record. All other bindings data retrieve data from database.

### First child thread (currently MQTTResponderLoopThread)

- Performs connection for client shared between this and primary thread.
- Runs paho mqtt in 'blocking mode' (loop_forever)
- receives/subscribes to requests to 'catchup'
  - topic: replicate/request/instance-name
  - Puts request in the queue to be processed by the tertiary thread(s)
    - Includes the data_binding value from the user property of the message

### Second child thread(s) (currently MQTTResponderThread)

#### Monitors 'catchup' queue

- Connects to the broker.
- Retrieves the 'catchup' data from the database specified in the user property data_binding value
- Publishes 'catchup' data
  - topic: replicate/response/secondary-instance-clientid
  - UserProperty property: data_binding = data binding used to retrieve the data
- Disconnects from broker when last message has been published (on_publish callback)
