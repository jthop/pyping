#!/usr/bin/env python3
#---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import os
import sys
import logging
import pkg_resources
import json
from dhcp import DHCPv4Client

from flask import Flask

############################################

__version__ = '0.0.3'

IFACE = 'eno3'
MAC = 'aa:bb:cc:11:22:34'

PIP_VERSION = os.environ.get('PYTHON_PIP_VERSION', '1.0')
PYTHON_VERSION = os.environ.get('PYTHON_VERSION', '1.0')
DOCKER_HOSTNAME = os.environ.get('HOSTNAME', 'NO_HOSTNAME')
SERVER_SOFTWARE = os.environ.get('SERVER_SOFTWARE', 'server/1.0')
SERVER_VERSION = SERVER_SOFTWARE.split('/')[1]
FLASK_VERSION = pkg_resources.get_distribution("flask").version
HOST_VERSION = __version__

app = Flask(__name__)
app.config.update(
    SECRET_KEY='asdf1234foo@bar',
    HOST_VERSION=HOST_VERSION,
    PYTHON_VERSION=PYTHON_VERSION,
    PIP_VERSION=PIP_VERSION,
    DOCKER_HOSTNAME=DOCKER_HOSTNAME,
    SERVER_SOFTWARE=SERVER_SOFTWARE,
    SERVER_VERSION=SERVER_VERSION
)
handler = logging.StreamHandler(sys.stdout)
#app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)


app.logger.info('flask v {} starting up.'.format(FLASK_VERSION))
app.logger.info('host v {} initialized.'.format(HOST_VERSION))
app.logger.info('pinger using python v {} and pip v {}'.format(
  PYTHON_VERSION, PIP_VERSION))
app.logger.info('pinger hosted via {} on docker host {}'.format(
  SERVER_SOFTWARE, DOCKER_HOSTNAME))


############################################

@app.route("/")
def index():
    """Fake handler"""
    return '<html>complete</html>'

@app.route("/_dhcp/<mac>")
def dhcp(mac=MAC):
    client = DHCPv4Client()
    try:
        results = client.go(mac)
    except Exception as e:
        results = { 'alive': False, 'e': str(e) }
    return json.dumps(results)

@app.route("/_env")
def all_env():
    return str(os.environ)
