#
#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

''' Run mqttreplicate 'standalone'.'''
import argparse
import sys

from pathlib import Path

if __name__ == '__main__':
    typical_install_locations = {
        'pip': {
            'weewx_root': '~/weewx-data/',
            'user_root': '~/weewx-data/bin/user/',
            'bin_root': None,
            'config_file': '~/weewx-data/weewx.conf',
        },
        'package': {
            'weewx_root': '/etc/weewx/',
            'user_root': '/etc/weewx/bin/user/',
            'bin_root': '/usr/share/weewx/',
            'config_file': '/etc/weewx/weewx.conf',
        },
        'git': {
            'weewx_root': '~/weewx-data/',
            'user_root': '~/weewx-data/bin/user/',
            'bin_root': '~/weewx/src',
            'config_file': '~/weewx-data/weewx.conf',
        },
    }

    def common_options(parser):
        ''' Setup parsing for options that are common between the requester and responder. '''
        parser.add_argument("--install-type", choices=["pip", "package", "git"],
                            help="The type of install used.",
                            default="package")

        parser.add_argument("--weewx-root",
                            help="The WeeWX root directory.",)
        parser.add_argument("--user-root",
                            help="The user directory.",)
        parser.add_argument("--bin-root",
                            help="The location of the WeeWX executables.",)
        parser.add_argument("----config-file",
                            help="The WeeWX configuration.",)

    def requester_options(parser):
        ''' Setup parser when running as the requester. '''
        subparser = parser.add_parser('requester',
                                      description='ToDo: ',
                                      formatter_class=argparse.RawDescriptionHelpFormatter)

        common_options(subparser)
        return subparser

    def process_locations(options):
        ''' Set the location of WeeWX bits and pieces. '''
        locations = {
            'weewx_root': str(Path(options.weewx_root if options.weewx_root
                                   else typical_install_locations[options.install_type]['weewx_root']).expanduser()),
            'user_root': str(Path(options.user_root if options.user_root
                                  else typical_install_locations[options.install_type]['user_root']).expanduser()),
            'bin_root': str(Path(options.bin_root if options.bin_root
                                 else typical_install_locations[options.install_type]['bin_root']).expanduser()),
            'config_file': str(Path(options.config_file if options.config_file
                                    else typical_install_locations[options.install_type]['config_file']).expanduser()),
        }

        if locations['bin_root']:
            sys.path.append(locations['bin_root'])

        return locations

    def setup_config(config_file):
        ''' Setup the config file. '''
        # Need to setup python path before importing - pylint: disable=import-outside-toplevel
        import weewx
        import weecfg
        import weeutil
        # Need to setup python path before importing - pylint: enable=import-outside-toplevel
        _config_path, config_dict = weecfg.read_config(config_file)
        weewx.debug = 1
        config_dict['debug'] = 1
        weeutil.logger.setup('wee-replicate', config_dict)

        del config_dict['Engine']
        config_dict['Engine'] = {}
        config_dict['Engine']['Services'] = {}

        return config_dict

    def main():
        """ Run it."""

        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--version', action='version', version="MQTTReplicate version is ToDo:")

        subparsers = arg_parser.add_subparsers(dest='command')
        _ = requester_options(subparsers)

        options = arg_parser.parse_args()
        locations = process_locations(options)
        # Need to setup python path before importing - pylint: disable=import-outside-toplevel
        import weewx
        import mqttreplicate
        # Need to setup python path before importing - pylint: enable
        # =import-outside-toplevel

        config_dict = setup_config(locations['config_file'])

        engine = weewx.engine.DummyEngine(config_dict)

        if options.command == 'requester':
            mqtt_requester = mqttreplicate.MQTTRequester(config_dict, engine)
            # try:
            #     for _packet in mqtt_requester.genLoopPackets():
            #         pass
            # except (KeyboardInterrupt, Exception):  # pylint: disable=broad-exception-caught
            mqtt_requester.closePort()
        else:
            arg_parser.print_help()

main()
