#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

from os import environ
import pkg_resources
import yaml as _yaml
from munch import munchify

__version__ = '2.2'

######################################


# misc version info, stored in ver dictionary: app.config['ver']
ver = {}
ver['pip_version'] = environ.get('PYTHON_PIP_VERSION', '1.0')
ver['python_version'] = environ.get('PYTHON_VERSION', '1.0')
ver['server_software'] = environ.get('SERVER_SOFTWARE', 'server/1.0')
ver['flask_version'] = pkg_resources.get_distribution("flask").version
ver['redis_version'] = pkg_resources.get_distribution("redis").version

# Do our "live in Docker" vs "running in Flask debugger" setup
if environ.get('INSIDE_CONTAINER'):
    redis_host = environ.get('REDIS_HOSTNAME', 'redis')
    mongo_host = environ.get('MONGODB_HOSTNAME', 'mongodb')
else:
    redis_host = environ.get('REDIS_HOSTNAME', 'localhost')
    mongo_host = environ.get('MONGODB_HOSTNAME', 'mongodb')

d = environ.get('HOSTNAME', None)
if d:
    docker_hostname = '-'.join([d[:4], d[4:8], d[8:]])
else:
    docker_hostname = 'a-b-c'

# read in user config
site_cfg = './config/site.yml'
# Read YAML file
with open(site_cfg, 'r') as stream:
    parsed_yaml = _yaml.safe_load(stream)
yaml = munchify(parsed_yaml)


class Config(object):

    # to be set in main.py
    APP_NAME = None
    APP_VERSION = None
    HEXDIGEST = None

    SECRET_KEY = environ.get('FLASK_SECRET', 'is-this-even-necessary')
    JSONIFY_PRETTYPRINT_REGULAR = True
    # VER used for mainly useless version info
    VER = ver
    YAML = yaml

    DOCKER_HOSTNAME = docker_hostname
    REDIS_URL = f'redis://{redis_host}:6379/0'
    LOG_FORMAT = '[%(asctime)s %(name)9s@%(lineno)-3d %(levelname)8s]  %(message)s'
    LOG_FORMAT_DATE = '%Y-%m-%d %H:%M:%S'
    MAC_PLACEHOLDER = '<<MAC>>'
    TIMEOUT = 3
    SEND_NOTIFICATIONS = True
