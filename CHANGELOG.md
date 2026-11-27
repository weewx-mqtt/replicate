# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

- Catchup publishing is batched (`batch_size`, default 200, and `batch_sleep`), with in-flight
  publishes drained at each batch boundary and again at shutdown (`wait_for_inflight`).
  `throttle_count` and `throttle_sleep` are replaced.
- Direct logging and the bounded in-flight drain now come from the shared `user.mqttcommon` (API 1.3).
- The MQTT connection now runs on paho's network loop instead of a custom loop thread; broker
  connectivity retries automatically until the broker is reachable, and catchup publishing is bounded
  by a fixed in-flight window before further records are sent.

## [1.1.0]

- Start the changelog. Earlier release history is in the git history and GitHub releases.
