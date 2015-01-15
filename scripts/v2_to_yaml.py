"""Convert an Omnipresence 2.x "legacy" configuration file to YAML."""


import argparse
import sys

import yaml

from omnipresence.config import OmnipresenceConfigParser


def convert(v2_file):
    """Return a configuration dict suitable for YAML serialization based
    on the settings in the legacy file *v2_file*."""
    connection = {}
    config = OmnipresenceConfigParser()
    config.readfp(v2_file)
    # Handler and command sections.
    if config.has_section('channels'):
        for channel in config.options('channels'):
            key = 'private' if channel == '@' else ('channel ' + channel)
            connection[key] = {'plugin ' + plugin: True for plugin
                               in config.getspacelist('channels', channel)}
        config.remove_section('channels')
    if config.has_section('commands'):
        for keyword in config.options('commands'):
            plugin = config.get('commands', keyword)
            key = 'plugin ' + plugin
            connection.setdefault(key, []).append(keyword)
        config.remove_section('commands')
    # Treat all other sections as containers for plugin settings.
    for section in config.sections():
        prefix = '' if section == 'core' else (section + '.')
        for option in config.options(section):
            key = 'set ' + prefix + option
            if section == 'core' and option == 'port':
                value = config.getint(section, option)
            elif section == 'core' and option == 'ssl':
                value = config.getboolean(section, option)
            elif section == 'core' and option == 'command_prefixes':
                value = config.getspacelist(section, option, raw=True)
            else:
                value = config.get(section, option)
            connection[key] = value
    return {'connection default': connection}


def main():
    parser = argparse.ArgumentParser(
        description=sys.modules[__name__].__doc__)
    parser.add_argument(
        'v2_file', metavar='V2', type=argparse.FileType(),
        help='2.x file to convert')
    parser.add_argument(
        'yaml_file', metavar='YAML', type=argparse.FileType('w'),
        help='output YAML file')
    args = parser.parse_args()
    args.yaml_file.write(yaml.dump(convert(args.v2_file)))


if __name__ == '__main__':
    main()
