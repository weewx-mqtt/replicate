""" Installer for mqttreplicate service.

To uninstall run
wee_extension --uninstall=mqttreplicate
"""

from io import StringIO

import configobj

from weecfg.extension import ExtensionInstaller

VERSION = "1.0.0-rc02a"

MQTTREPLICATE_CONFIG = """
[MQTTReplicate]
    driver = user.mqttreplicate

    [[Requester]]
        [[[weewx]]]
            # This is a remote binding
            # And must match a binding in the 'Responder' configuration              
            [[[[wx_binding]]]]
                type = main
                # This is the local database bindingg
                secondary_data_binding = wx_binding

    [[Responder]]
        enable = false
        host = localhost
        [[[weewx]]]
            [[[[wx_binding]]]]
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
