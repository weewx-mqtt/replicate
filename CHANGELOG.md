# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

- The MQTT connection now runs on paho's network loop instead of a custom loop thread; broker
  connectivity retries automatically until the broker is reachable, and catchup publishing is bounded
  by a fixed in-flight window before further records are sent.

## [1.1.0]

- Start the changelog. Earlier release history is in the git history and GitHub releases.
