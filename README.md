# weewx-mqtt/replicate

## Description

Using MQTT V5 request/respond functionality, replicate WeeWX databases.
The requester, a WeeWX driver, is the secondary (copy) database(s).
The responder, a WeeWX service, is the primary database(s)

## Preqrequisites

|Prerequisite                                                   |Version                  |
|---------------------------------------------------------------|-------------------------|
|[WeeWX](https://www.weewx.com)                                 |5.0.0 or higher          |
|[Python](https://www.python.org)                               |3.9.13 or higher         |
|[Paho MQTT Python client](https://pypi.org/project/paho-mqtt/) |1.6.1 or higher          |
|[MQTT](https://mqtt.org)                                       |5 or higher              |

*Note:* Early versions of Python 3 may work, but have not been explicitly tested.

*Note:* Not all 'supported' versions of the Paho MQTT client have been tested.

*Note:* Not all 'supported' versions of MQTT have been tested.

## Installation

This extension is installed using the [weectl extension utility](https://www.weewx.com/docs/5.0/utilities/weectl-extension/).
The latest release can be installed with the invocation

```shell
weectl extension install https://github.com/weewx-mqtt/replicate/archive/refs/tags/latest.zip
```

If a specific version is desired, the invocation would look like

```shell
weectl extension install https://github.com/weewx-mqtt/replicate/archive/refs/tags/vX.Y.Z.zip
```

where X.Y.Z is the release.
The list of releases can be found at [https://github.com/weewx-mqtt/replicate/releases](https://github.com/weewx-mqtt/replicate/releases).

The version under development can be installed from the master branch using the following invocation

```shell
weectl extension install https://github.com/weewx-mqtt/replicate/archive/master.zip
```

Where `master` is the branch name.

*Note:* WeeWX 'package' installs add the user that performed the install to the `weewx` group.
This means that this user should not need to use `sudo` to install the `weewx-mqtt/replicate` extension.
**But** in order to for this update to the `weewx` group to take affect, the user has to have logged out/in at least once or use one of the other methods that can be found on the web

*Note:* WeeWX pip installs that install WeeWX into a `Python virtual environment`, must 'activate' the environment performing the install. A typical invocation would look like this.

```shell
source ~/weewx-venv/bin/activate
```

## Customizing

## Getting Help

Feel free to [open an issue](https://github.com/weewx-mqtt/replicate/issues/new),
[start a discussion in github](https://github.com/weewx-mqtt/replicate/discussions/new),
or [post on WeeWX google group](https://groups.google.com/g/weewx-user).
When doing so, see [Help! Posting to weewx user](https://github.com/weewx/weewx/wiki/Help!-Posting-to-weewx-user)
for information on capturing the log.
And yes, **capturing the log from WeeWX startup** makes debugging much easeier.
