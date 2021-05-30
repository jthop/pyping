#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import os
import logging
import pkg_resources
import pickle
import importlib
import time
from datetime import datetime

from flask import Flask, request, render_template
from pymongo import MongoClient
import redis

import config as cfg
import service
import notification

############################################

__site_name__ = 'pyping'
__version__ = 'v0.7.5-beta'
__build__ = 117


PIP_VERSION = os.environ.get('PYTHON_PIP_VERSION', '1.0')
PYTHON_VERSION = os.environ.get('PYTHON_VERSION', '1.0')
SERVER_SOFTWARE = os.environ.get('SERVER_SOFTWARE', 'server/1.0')
SERVER_VERSION = SERVER_SOFTWARE.split('/')[1]
FLASK_VERSION = pkg_resources.get_distribution("flask").version
PYMONGO_VERSION = pkg_resources.get_distribution("pymongo").version
REDIS_VERSION = pkg_resources.get_distribution("redis").version

d = os.environ.get('HOSTNAME', 'NO_HOSTNAME')
if d:
    DOCKER_HOSTNAME = '-'.join([d[:4], d[4:8], d[8:]])
else:
    DOCKER_HOSTNAME = 'a-b-c'


def log_credits():
    app.logger.info('--------------------------------------')
    app.logger.info(
        f'starting {__site_name__} {__version__} build {__build__}'
    )
    app.logger.info('by @jthop <jh@mode14.com>')
    app.logger.info(f'imported cfg v{cfg.__version__}')
    app.logger.info(f'imported service v{service.__version__}')
    app.logger.info(f'imported notification v{notification.__version__}')
    app.logger.info('--------------------------------------')
    app.logger.info(f'imported pymongo v{PYMONGO_VERSION}')
    app.logger.info(f'imported redis v{REDIS_VERSION}')
    app.logger.info('--------------------------------------')
    app.logger.info(f'python v{PYTHON_VERSION}')
    app.logger.info(f'environment: pip v{PIP_VERSION}')
    app.logger.info(f'flask v{FLASK_VERSION}')
    app.logger.info(f'wsgi: {SERVER_SOFTWARE}')
    app.logger.info(f'docker host: {DOCKER_HOSTNAME}')
    app.logger.info('--------------------------------------')


############################################

r = redis.StrictRedis(host=cfg.REDIS_HOST)
app = Flask(__name__)
logging.basicConfig(
     format=cfg.LOG_FORMAT,
     datefmt=cfg.LOG_FORMAT_DATE,
     level=logging.DEBUG
)
app.config.update(
    SECRET_KEY=cfg.FLASK_SECRET,
    JSONIFY_PRETTYPRINT_REGULAR=True,
    APP_NAME=__site_name__,
    APP_VERSION=__version__,
    APP_BUILD=__build__,
    PYTHON_VERSION=PYTHON_VERSION,
    DOCKER_HOSTNAME=DOCKER_HOSTNAME
)
log_credits()

############################################


@app.route("/")
def index():
    """
    Handler for the main page.  This displays the cached
    (hopefully) results.
    """

    p = Pinger.load()
    i = Mongo().fetch()
    return render_template('index.html', pinger=p, incidents=i)


@app.route("/_cron")
def cron():
    """
    The primary checker.  This is the endpoint run each
    time cron runs the checker.  We will check all services,
    and then send notifications if necessary, as well as
    insert details into Mongo.
    """

    p = Pinger.load()
    for service in p.services:
        service.check()
        if service.is_alive:
            # Service is UP
            if service.get_n() > 2:
                # back up - we should write incident to mongodb
                m = Mongo()
                m.insert(service.freeze)
                # send backup notifications
                body = '{} is BACK UP after {} pings.'.format(
                    service.pretty_name,
                    service.get_n()
                )
                msg = notification.Notification(
                    service.pretty_name,
                    body
                )
                msg.send()
                service.reset_n()  # n=0
        else:
            # Service is DOWN
            service.incr_n()
            if service.get_n() == 2:
                # write to mongo
                m = Mongo()
                m.insert(service.freeze)
                # now send msg
                body = '{} just went down. {}'.format(
                    service.pretty_name,
                    service.response
                )
                msg = notification.Notification(
                    service.pretty_name,
                    body
                )
                msg.send()
    p.save()
    return '<html>cron complete</html>'


@app.route("/_health/<patient>")
def healthcheck(patient='vagrant'):
    """
    health checks for pyping as well as cron, since cron has no server.
    call like: app.get( http://pyping/_health/self )
    or app.get( http://pyping/_health/cron )
    """

    app.logger.info(f'HEALTHCHECK for: <{patient}> returned 200')
    return {'success': True}, 200    # will be returned with jsonify


@app.errorhandler(404)
def not_found(e):
    """
    basic 404 handler
    """

    app.logger.info(f'serving 404 for: {request.path}')
    return render_template("404.html")


@app.route("/_test")
def tester():
    """
    Simple endpoint to test notifications.  This is intended for
    debugging purposes only.
    """

    msg = notification.Notification('test sub', 'test body')
    msg.send()
    return '<html>test complete</html>'


@app.route("/_clear/redis")
def clear_all_redis():
    """
    The endpoint to initiate to clearing of all redis keys.
    """

    if Pinger.clear():
        return '<html>clear complete</html>'


@app.route("/_clear/mongo")
def clear_all_mongo():
    """
    Endpoint to initiate the deletion of all Mongo documents.
    """

    m = Mongo()
    if m.clear_all():
        return '<html>clear complete</html>'
    else:
        h = 'Error locating cache'
        d = 'Could not load the cache OR load obj from file.  Serious issue.'
        return render_template(
          'error.html',
          status_code=400,
          headline=h,
          description=d)


@app.route("/_env")
def all_env():
    """
    Returns all ENV variables.  Intended for debugging.
    """
    
    return str(os.environ)


@app.route("/_dump")
def dump_pinger():
    """
    Return a pretty print of all the service objects.  This 
    endpoint was intended for debuging only.
    """

    p = Pinger.load()
    if p:
        services = p.services
        serialized = []
        for service in services:
            d = service.to_dict()
            serialized.append(d)
        pinger = {
          'created': p.created,
          'services': serialized
        }
        return pinger, 200   # will be returned with jsonify
    else:
        h = 'Error dumping'
        d = 'Error finding cazche or creating obj via file'
        return render_template(
          'error.html',
          status_code=400,
          headline=h,
          description=d)


############################################

@app.template_filter('fmt_timestamp')
def fmt_timestamp(s):
    """
    Jinja filter to format date/time from timestamp.
    """

    dt = datetime.datetime.fromtimestamp(int(s))
    pretty_time = ts.strftime('%d/%m/%y %I:%M %p')
    return a


class Mongo:
    def __init__(self):
        """
        Constructor, mainly sets up Mongo
        connection.
        """

        client = MongoClient(
          cfg.MONGO_HOST,
          username=cfg.MONGO_USER,
          password=cfg.MONGO_PASS,
        )
        self.db = client[cfg.MONGODB_DATABASE]
        self.collection = self.db['incidents']
        # client.admin.authenticate(MONGO_USER, MONGO_PASS)
        app.logger.debug('ATTENTION! Mongo class instantiated.')

    def insert(self, data):
        """
        Insert new document into our Mongo collection.
        """

        _id = self.collection.insert_one(data)
        app.logger.debug('Mongo insert of {}.'.format(data))
        return _id

    def fetch(self, x=cfg.DEFAULT_MONGO_ROWS):
        """
        Fetch most recent 10 rows for homepage.
        """

        cursor = self.collection.find().sort('now', -1).limit(x)
        app.logger.debug('Mongo fetch')
        return cursor

    def clear_all(self):
        """
        Clear all keys from Redis.
        """

        try:
            cursor = self.collection.find({})
            self.collection.drop(cursor)
            app.logger.debug('Mongo dropped entire collection')
        except Exception as e:
            app.logger.error(str(e))
            return False
        else:
            return True


class Pinger:
    """
    Pinger object we can cache in Redis so the website
    can run without having to do it's own checks.
    """

    def __init__(self):
        """
        Used when loading initial data from file.  Reads
        config file and dynamically instantiates the
        correct object types for each service.
        """

        services = cfg.yaml.services
        epoch = datetime.utcfromtimestamp(0)
        self.updated = epoch
        self.created = epoch
        self._services = []
        for svc in services:
            app.logger.debug('loading: {}-{}'.format(
                svc.get('name'), svc.get('service_type')))

            """
            copy the config dict and pop unneeded vals - 
            if we didn't pop service_type it will cause error
            as it's not needed in constructor, and if we pop 
            without copying, we will pop off the actual config 
            dict
            """

            shallow_copy = svc.copy()
            shallow_copy.pop('service_type', None)

            module = importlib.import_module('service')
            klass_name = svc.get('service_type').upper()
            klass = getattr(module, class_name)
            instance = klass(**shallow_copy)

            self._services.append(instance)

    @property
    def services(self):
        """
        Getter to return all of the site services.
        """

        return self._services

    @property
    def all_alive(self):
        """
        Check if all services are alive.  If so we have a 
        special banner for top of page.
        """

        app.logger.debug('Someone wants to know if all are ALIVE')
        for service in self._services:
            if not service.is_alive:
                return False
        return True

    @property
    def all_dead(self):
        """
        Check if all services are down.  If so we have a 
        special banner for top of page.
        """

        app.logger.debug('Someone wants to know if all are DEAD')
        for service in self._services:
            if service.is_alive:
                return False
        return True

    @property
    def long_ago(self):
        """
        One of those "How long ago" sections
        on the website.  5 minutes, 2 minutes,
        just now...
        """

        if not self.updated:
            return 'Never?'
        now = datetime.now()
        elapsed_time = now - self.updated
        secs = elapsed_time.total_seconds()

        if secs > 1200:
            # 20 minutes
            return 'a while ago'
        elif secs > 900:
            return 'about 15 minutes ago'
        elif secs > 600:
            return 'about 10 minutes ago'
        elif secs > 300:
            return 'about 5 minutes ago'
        elif secs > 240:
            return 'about 4 minutes ago'
        elif secs > 180:
            return 'about 3 minutes ago'
        elif secs > 120:
            return 'about 2 minutes ago'
        elif secs > 60:
            return 'about 1 minute ago'
        elif secs > 30:
            return 'about 30 seconds ago'
        else:
            return 'just now'
        return elapsed_time.total_seconds()

    def serialize(self):
        """
        Prepare the object to be stored in
        Redis.
        """

        return pickle.dumps(self)

    def save(self):
        """
        After check, serialize cache and save to Redis.
        This way the website can load aoo data without
        having to re-check sites itself.
        """

        app.logger.info('SAVING cache now!')
        self.updated = datetime.now()
        r.set(cfg.yaml.get('url'), self.serialize())

    @classmethod
    def load(cls):
        """
        Attempt to fetch results from cache.
        If cache is a MISS, load the initial
        data from file.
        """

        cache = r.get(cfg.yaml.get('url'))
        if cache:
            # Load from CACHE
            app.logger.info('cache HIT! Loading from cache.')
            return pickle.loads(cache)
        else:
            # Load from FILE
            app.logger.info('cache MISS. Loading from file.')
            p = Pinger()
            return p

    @classmethod
    def clear(cls):
        """
        Delete the Redis cache.  This method is
        intended for debugging.
        """

        r.delete(cfg.yaml.get('url'))
        return True


############################################
