#
#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

''' Run mqttreplicate 'standalone'.'''
import argparse
import sys
import time

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
        parser.add_argument("--debug", choices=["on", "off"], default="on",
                            help="Turn WeeWX debug on/off.",)

        parser.add_argument("--weewx-root",
                            help="The WeeWX root directory.",)
        parser.add_argument("--user-root",
                            help="The user directory.",)
        parser.add_argument("--bin-root",
                            help="The location of the WeeWX executables.",)
        parser.add_argument("--config-file",
                            help="The WeeWX configuration.",)

    def requester_options(parser):
        ''' Setup parser when running as the requester. '''
        subparser = parser.add_parser('requester',
                                      description='ToDo: ',
                                      formatter_class=argparse.RawDescriptionHelpFormatter)

        common_options(subparser)

        subparser.add_argument('--archive-delay', type=int, default=30,
                               help='The simulated archive delay in seconds.')

        return subparser

    def responder_options(parser):
        ''' Setup parser when running as the responder. '''
        subparser = parser.add_parser('responder',
                                      description='ToDo: ',
                                      formatter_class=argparse.RawDescriptionHelpFormatter)

        common_options(subparser)

        return subparser

    def process_locations(options):
        ''' Set the location of WeeWX bits and pieces. '''
        locations = {
            'weewx_root': options.weewx_root if options.weewx_root else typical_install_locations[options.install_type]['weewx_root'],
            'user_root': options.user_root if options.user_root else typical_install_locations[options.install_type]['user_root'],
            'bin_root': options.bin_root if options.bin_root else typical_install_locations[options.install_type]['bin_root'],
            'config_file': options.config_file if options.config_file else typical_install_locations[options.install_type]['config_file'],
        }

        for key, value in locations.items():
            locations[key] = value if value is None else str(Path(value).expanduser())

        if locations['bin_root']:
            sys.path.append(locations['bin_root'])

        if locations['user_root']:
            sys.path.append(str(Path(locations['user_root']).parent))

        return locations

    def setup_config(config_file, debug):
        ''' Setup the config file. '''
        # Need to setup python path before importing - pylint: disable=import-outside-toplevel
        import weecfg
        import weeutil.logger
        # Need to setup python path before importing - pylint: enable=import-outside-toplevel

        _config_path, config_dict = weecfg.read_config(config_file)

        config_dict['debug'] = 1 if debug == 'on' else 0
        weeutil.logger.setup('wee-replicate', config_dict)

        config_dict['Station'] = {
            'altitude': [0, 'foot'],
            'latitude': 0.0,
            'longitude': 0.0,
        }

        config_dict['Engine'] = {}
        config_dict['Engine']['Services'] = {}

        return config_dict

    def calculate_sleep(archive_interval, archive_delay):
        ''' Calculate the amount of time to sleep until the start of the next interval. '''
        current_time = int(time.time() + 0.5)
        end_period_ts = (int(current_time / archive_interval) + 1) * archive_interval
        end_delay_ts = end_period_ts + archive_delay
        return end_delay_ts - current_time

    def run_requester(options, config_dict, engine):
        ''' Run as a requester in 'standalone mode'. '''
        # Need to setup python path before importing - pylint: disable=import-outside-toplevel
        import weeutil
        import mqttreplicate
        # Need to setup python path before importing - pylint: enable=import-outside-toplevel

        archive_delay = options.archive_delay
        stn_dict = config_dict['MQTTReplicate']['Requester']
        archive_interval = weeutil.weeutil.to_int(stn_dict.get('archive_interval', 300))

        mqtt_requester = mqttreplicate.MQTTRequester(config_dict, engine)

        for record in mqtt_requester.genStartupRecords(None):
            print("REC:   ",
                  weeutil.weeutil.timestamp_to_string(record['dateTime']),
                  weeutil.weeutil.to_sorted_string(record))

        sleep_amount = calculate_sleep(archive_interval, archive_delay)
        print(f"Sleeping {int(sleep_amount)} seconds")
        time.sleep(sleep_amount)

        for record in mqtt_requester.genArchiveRecords(None):
            print("REC:   ",
                  weeutil.weeutil.timestamp_to_string(record['dateTime']),
                  weeutil.weeutil.to_sorted_string(record))

        mqtt_requester.closePort()

    def run_responder(config_dict, engine):
        ''' Run as a responder in 'standalone mode'. '''
        config_dict['MQTTReplicate']['Responder']['enable'] = True
        # Need to setup python path before importing - pylint: disable=import-outside-toplevel
        import mqttreplicate
        # Need to setup python path before importing - pylint: enable=import-outside-toplevel
        mqttreplicate.MQTTResponder(engine, config_dict)

    def main():
        """ Run it."""

        arg_parser = argparse.ArgumentParser()
        arg_parser.add_argument('--version', action='version', version="MQTTReplicate version is ToDo:")

        subparsers = arg_parser.add_subparsers(dest='command')
        _ = requester_options(subparsers)
        _ = responder_options(subparsers)

        options = arg_parser.parse_args()
        locations = process_locations(options)
        # Need to setup python path before importing - pylint: disable=import-outside-toplevel
        import weewx.engine
        # Need to setup python path before importing - pylint: enable=import-outside-toplevel

        config_dict = setup_config(locations['config_file'], options.debug)

        engine = weewx.engine.DummyEngine(config_dict)

        if options.command == 'requester':
            run_requester(options, config_dict, engine)
        elif options.command == 'responder':
            run_responder(config_dict, engine)
        else:
            arg_parser.print_help()

main()
