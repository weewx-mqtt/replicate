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

### Primary thread

- When instance is created
  - Thread is created to process data from responder (primary database(s)).
  - Request is made for all records later than last record in database(s).
    - Publishes to specific topic to request 'catchup' data be published to s;ecified 'catchup' topic.
The response will be processed in the secondary thread.

genStartupRecords

genArchiveRecords

genLoopPackets

- generates 'empty' packets

### Secondary thread

- Connects using paho mqtt client that is shared with primary thread.
- Subscribes to 'catchup' topic to receive 'catchup' data.
- Subscribes to 'archive' topic to receive 'archive' data.
- Runs paho mqtt in 'blocking mode' (loop_forever)
- When MQTT message is received
  - For 'main' database, data put into the queue to be processed by the primary thread (genStartupRecords or genArchiveRecords).
  - For other databases, database is updated directly.

## Responder

Consists of 3 threads

### Primary thread

thread creation

- All paho mqtt callbacks are handled in the secondary thread.
- When new_archive_record is raised, publishes archive data for all databases.

### Secondary thread (currently MQTTResponderLoopThread)

- Performs connection for client shared between this and primary thread.
- Runs paho mqtt in 'blocking mode' (loop_forever)
- receives/subscribes to requests to 'catchup' on known topic
  - Puts request in the queue to be processed by the tertiary thread(s)

### Tertiary thread(s) (currently MQTTResponderThread)

- Monitors 'catchup' queue
- Publishes 'catchup' data to topic specified in request message
