""" Installer for mqttreplicate service.

To uninstall run
wee_extension --uninstall=mqttreplicate
"""

from io import StringIO

import configobj

from weecfg.extension import ExtensionInstaller

VERSION = "1.0.0-rc03a"

MQTTREPLICATE_CONFIG = """
[MQTTReplicate]
    driver = user.mqttreplicate

    # Configuration data for the requester (the WeeWX driver).
    [[Requester]]
        # The time between between generating loop packets.
        # The default value is 2.5.
        loop_interval = 2.5

        # The WeeWX archive interval.
        # The default value is 300.
        archive_interval = 300

        # When performing 'catch up', the maximum number of times to see if the necessary data is available.
        # The default value is 2.
        startup_max_tries = 2

        # When performing 'catch up', the amount of time to `wait` for the necessary data.
        # The default value is 10.
        startup_wait_before_retry = 10

        # When generating archive records, the maximum number of times to see if the necessary data is available.
        # The default value is 2.
        archive_max_tries = 2

        # When generating archvie records, the amount of time to `wait` for the necessary data.
        # The default value is 10.
        archive_wait_before_retry = 10

        # The MQTT QOS when subscribing to a topic.
        # The default value is 1.
        subscribe_qos = 1

        # The MQTT QOS when publishing to a topic.
        # The default value is 1.
        publish_qos = 1

        # The topic that the replication data is published to.
        # And therefore the topic that is subscribed to receive it.
        # The default value is replicate/archive.
        archive_topic = replicate/archive

        # The MQTT server.
        # The default value is localhost.
        host = localhost

        # The port to connect to.
        # The default value is 1883.
        port = 1883

        # Maximum period in seconds allowed between communications with the broker.
        # The default is 60.
        keepalive = 60

        # Controls the MQTT logging.
        # The default value is false.
        log_mqtt = false

        # The prefix for response topic.
        # The default value is replicate/response.
        # The final default value is 'replicate/response/{MQTT client id}'.
        # The response topic is the topic that the responser publishes 'catchup'/'backfill' data to.
        # And therefore the response topic is the topic that the requester subscribes to.
        response_topic = replicate/response

        # The prefix for the request topic.
        # Each replicating instance will have a unique request_topic
        # The default value is replicate/request.
        # The final default value is 'replicate/request/{instance name}'
        # The request topic is the topic that the requester uses to request 'catchup'/'backfill' data.
        request_topic = replicate/request

        # This configures the replicating instance(s).
        # Each replicating instance name needs to match an entry in a MQTTReplicate [[Responder]] section.
        # A replicating instance consists of a set of primary (source) databases to replicate.
        [[[weewx]]]
            # This is a source/remote binding
            # And must match a binding in the 'Responder' configuration
            [[[[wx_binding]]]]
                # The main data binding is the database that WeeWX uses to store the archive data.
                # Typically the data binding is 'wx_binding' and the database name is 'weewx'.
                type = main
                # This is the target/local database binding
                secondary_data_binding = wx_binding

    [[Responder]]
        enable = false

        # When retrieving secondary data to be published, replicated the largest difference in time that is accepted.
        # Some extensions do not force the time to an archive interval, so the WeeWX default value of 'None' does not always work.
        # The default value is 60.
        delta = 60

        # The maximum number of responser threads to create.
        # The default value is 1.
        # DEPRECATED - DO NOT USE
        # max_responder_threads = 1

        # The MQTT QOS when subscribing to a topic.
        # The default value is 1.
        subscribe_qos = 1

        # The MQTT QOS when publishing to a topic.
        # The default value is 1.
        publish_qos = 1

        # The topic that the replication data is published to.
        # And therefore the topic that is subscribed to receive it.
        # The default value is replicate/archive.
        archive_topic = replicate/archive

        # The MQTT server.
        # The default value is localhost.
        host = localhost

        # The port to connect to.
        # The default value is 1883.
        port = 1883

        # Maximum period in seconds allowed between communications with the broker.
        # The default is 60.
        keepalive = 60

        # Controls the MQTT logging.
        # The default value is false.
        log_mqtt = false

        # The prefix for the request topic.
        # Each replicating instance will have a unique request_topic
        # The default value is replicate/request.
        # The final default value is 'replicate/request/{instance name}'
        # The request topic is the topic that the requester uses to request 'catchup'/'backfill' data.
        # So, the responser subscribes to this topic
        request_topic = replicate/request

        # This configures the replicating instance.
        # There can be only one replicating instance in a running WeeWX instance
        # The name must be unique across all running MQTTReplicate/responders.
        # This needs to match an entry in the [[Requester]] section.
        # A replicating instance consists of a set of primary (source) databases to replicate.
        [[[weewx]]]
            # This is a primary data binding
            # And must match a binding in the 'Requester' configuration
            [[[[wx_binding]]]]
                # The main data binding is the database that WeeWX uses to store the archive data.
                # Typically the data binding is 'wx_binding' and the database name is 'weewx'.
                type = main
"""

def loader():
    """ Load and return the extension installer. """
    return MQTTReplicateInstaller()

class MQTTReplicateInstaller(ExtensionInstaller):
    """ The extension installer. """
    def __init__(self):

        install_dict = {
            'version': VERSION,
            'name': 'MQTTReplicate',
            # add a leading space, so that long versions does not run into the description
            'description': ' Replicate WeeWX data to a MQTT broker.',
            'author': "Rich Bell",
            'author_email': "bellrichm@gmail.com",
            'files': [('bin/user', ['bin/user/mqttreplicate.py'])]
        }

        mqttreplicate_dict = configobj.ConfigObj(StringIO(MQTTREPLICATE_CONFIG))
        install_dict['config'] = mqttreplicate_dict
        # ToDo: Better service group?
        install_dict['restful_services'] = 'user.mqttreplicate.MQTTResponder'

        super(MQTTReplicateInstaller, self).__init__(install_dict)
