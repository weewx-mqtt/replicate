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

The MQTT connection runs on paho's network loop, so a broker that is unavailable at startup is
retried automatically until it connects; there is no connection retry setting to configure.

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
- Runs paho mqtt via the network loop (loop_start); the connection retries until it succeeds.
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

### First child thread (the responder pool)

- Receives/subscribes to requests to 'catchup'
  - topic: replicate/request/instance-name
  - Puts request in the queue to be processed by the responder threads
    - Includes the data_binding value from the user property of the message
- Publishes the requested records through the client shared with the network loop; the batch is
  bounded by a fixed in-flight window before the next publish is sent.

### Second child thread(s) (the responder threads)

#### Monitors 'catchup' queue

- Retrieves the 'catchup' data from the database specified in the user property data_binding value
- Publishes 'catchup' data
  - topic: replicate/response/secondary-instance-clientid
  - UserProperty property: data_binding = data binding used to retrieve the data
- Waits for the batch's publishes to be confirmed (in-flight window) before taking the next request.
