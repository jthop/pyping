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


__version__ = '2.1'

######################################


# misc version info, stored in ver dictionary: app.config['ver']
ver = {}
ver['pip_version'] = environ.get('PYTHON_PIP_VERSION', '1.0')
ver['python_version'] = environ.get('PYTHON_VERSION', '1.0')
ver['server_software'] = environ.get('SERVER_SOFTWARE', 'server/1.0')
ver['flask_version'] = pkg_resources.get_distribution("flask").version
ver['pymongo_version'] = pkg_resources.get_distribution("pymongo").version
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


class dotdict(dict):
    """
    dot.notation access to dictionary attributes
    alternative to munchify.munch

      mydict = {'val':'it works'}
      mydict = dotdict(mydict)
      print(mydict.val)
      it works
    """

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


# read in user config
site_cfg = './config/site.yml'
# Read YAML file
with open(site_cfg, 'r') as stream:
    parsed_yaml = _yaml.safe_load(stream)
yaml = dotdict(parsed_yaml)


class Config(object):

    SECRET_KEY = environ.get('FLASK_SECRET', 'is-this-even-necessary')
    JSONIFY_PRETTYPRINT_REGULAR = True
    # app related config below
    VER = ver
    YAML = yaml

    DOCKER_HOSTNAME = docker_hostname
    REDIS_URL = f'redis://{redis_host}:6379/0'
    MONGO_HOST = mongo_host
    MONGO_USER = environ.get('MONGODB_USERNAME', 'root')
    MONGO_PASS = environ.get('MONGODB_PASSWORD', 'pass')
    MONGODB_DATABASE = environ.get('MONGODB_DATABASE', 'db')
    DEFAULT_MONGO_ROWS = 5
    LOG_FORMAT = '[%(asctime)s %(name)9s@%(lineno)-3d %(levelname)8s]  %(message)s'
    LOG_FORMAT_DATE = '%Y-%m-%d %H:%M:%S'
    MAC_PLACEHOLDER = '<<MAC>>'
    TIMEOUT = 3
    SEND_NOTIFICATIONS = True
