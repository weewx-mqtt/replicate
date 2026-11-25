#
#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

"""Test helpers shared by the MQTTReplicate unit tests."""

import configobj
import contextlib
import mock
from types import SimpleNamespace

from user.tests.unit.helpers import random_string


def create_requester_config(*, instance_name=None, primary_name=None, binding_name=None,
                            requester_overrides=None, topic_overrides=None):
    """ Build a requester config and return it with its generated names. """
    instance_name = random_string() if instance_name is None else instance_name
    primary_name = random_string() if primary_name is None else primary_name
    binding_name = random_string() if binding_name is None else binding_name

    topic = {'type': 'main', 'secondary_data_binding': binding_name}
    if topic_overrides:
        topic.update(topic_overrides)

    requester = {instance_name: {primary_name: topic}}
    if requester_overrides:
        requester.update(requester_overrides)

    config = configobj.ConfigObj({'MQTTReplicate': {'Requester': requester}})
    return config, instance_name, primary_name


def create_responder_service_config(*, instance_name=None, binding_name=None,
                                    include_instance=True, secondary_bindings=(),
                                    section_overrides=None):
    """ Build a responder config and return it with its generated names. """
    instance_name = random_string() if instance_name is None else instance_name
    binding_name = random_string() if binding_name is None else binding_name

    responder = {}
    if section_overrides:
        responder.update(section_overrides)
    if include_instance:
        instance = {}
        for secondary in secondary_bindings:
            instance[secondary] = {}
        instance[binding_name] = {'type': 'main'}
        responder[instance_name] = instance

    config = configobj.ConfigObj({'MQTTReplicate': {'Responder': responder}})
    return config, instance_name, binding_name


@contextlib.contextmanager
def patched_requester(*, random_int=None, log_direct=False):
    """ Patch the requester's collaborators, including Logger (required with threading). """
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch('user.mqttreplicate.threading'))
        stack.enter_context(mock.patch('user.mqttreplicate.paho.mqtt'))
        logger = stack.enter_context(mock.patch('user.mqttcommon.Logger'))
        manager = stack.enter_context(mock.patch('user.mqttreplicate.weewx.manager'))
        mqtt_client = stack.enter_context(mock.patch('user.mqttreplicate.MQTTClient'))
        loop_thread = stack.enter_context(mock.patch('user.mqttreplicate.MQTTRequesterLoopThread'))
        randint = None
        if random_int is not None:
            randint = stack.enter_context(mock.patch('user.mqttreplicate.random.randint', return_value=random_int))
        direct = None
        if log_direct:
            direct = stack.enter_context(mock.patch('user.mqttreplicate.log_direct'))
        yield SimpleNamespace(logger=logger, manager=manager, mqtt_client=mqtt_client,
                              loop_thread=loop_thread, randint=randint, log_direct=direct)


@contextlib.contextmanager
def patched_responder_service(*, queue=False, log_direct=False, use_json=False, paho=False,
                              random_int=None):
    """ Patch the responder's collaborators, including Logger (required with threading). """
    with contextlib.ExitStack() as stack:
        threading = stack.enter_context(mock.patch('user.mqttreplicate.threading'))
        logger = stack.enter_context(mock.patch('user.mqttcommon.Logger'))
        manager = stack.enter_context(mock.patch('user.mqttreplicate.weewx.manager'))
        responder_thread = stack.enter_context(mock.patch('user.mqttreplicate.MQTTResponderThread'))
        mqtt_client = stack.enter_context(mock.patch('user.mqttreplicate.MQTTClient'))
        loop_thread = stack.enter_context(mock.patch('user.mqttreplicate.MQTTResponderLoopThread'))

        queue_mock = stack.enter_context(mock.patch('user.mqttreplicate.queue.Queue')) if queue else None
        direct = stack.enter_context(mock.patch('user.mqttreplicate.log_direct')) if log_direct else None
        json_mock = stack.enter_context(mock.patch('user.mqttreplicate.json')) if use_json else None
        paho_mock = stack.enter_context(mock.patch('user.mqttreplicate.paho.mqtt')) if paho else None
        randint = None
        if random_int is not None:
            randint = stack.enter_context(mock.patch('user.mqttreplicate.random.randint', return_value=random_int))

        db_manager = mock.Mock()
        manager.open_manager.return_value = db_manager
        client = mock.Mock()
        mqtt_client.return_value = client

        yield SimpleNamespace(threading=threading, logger=logger, manager=manager,
                              responder_thread=responder_thread, mqtt_client=mqtt_client,
                              loop_thread=loop_thread, queue=queue_mock, log_direct=direct,
                              json=json_mock, paho=paho_mock, randint=randint,
                              db_manager=db_manager, client=client)
