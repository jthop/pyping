#!/usr/bin/env python3
#---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import os
import yaml as _yaml
from munch import munchify


__version__ = '1.2'

MONGO_USER = os.environ.get('MONGODB_USERNAME', 'root')
MONGO_PASS = os.environ.get('MONGODB_PASSWORD', 'pass')
MONGODB_DATABASE = os.environ.get('MONGODB_DATABASE', 'db')
DEFAULT_MONGO_ROWS = 5

LOG_FORMAT = '[%(asctime)s %(name)9s@%(lineno)-3d %(levelname)8s]  %(message)s'
LOG_FORMAT_DATE = '%Y-%m-%d %H:%M:%S'
MAC_PLACEHOLDER = '<<MAC>>'
FLASK_SECRET = 'asdf1234foo@bar'
TIMEOUT = 3

# used when testing.  who wants to spam themselves
SEND_NOTIFICATIONS = True

# Do our "live in Docker" vs "running in Flask debugger" setup
if os.environ.get('INSIDE_CONTAINER'):
  CONFIG_FILE = '/app/config/setup.yml'
  REDIS_HOST = 'redis'
  MONGO_HOST = os.environ.get('MONGODB_HOSTNAME', 'mongodb')
else:
  CONFIG_FILE = 'v/bind/config/setup.yml'
  REDIS_HOST = 'localhost'
  MONGO_HOST = os.environ.get('MONGODB_HOSTNAME', 'mongodb')


# Read YAML file
with open(CONFIG_FILE, 'r') as stream:
  parsed_yaml = _yaml.safe_load(stream)

yaml = munchify(parsed_yaml)

