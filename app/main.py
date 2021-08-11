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
import pickle
import importlib
from datetime import datetime

from flask import Flask, request, render_template
from redis import Redis
from pymongo import MongoClient

import app_config
import notification
import services

from last_bump import version as __version__
from last_bump import hexdigest
__app_name__ = 'pyping'

############################################

app = Flask(__name__, static_url_path='/static')
# Extra config - cleaner to do here
app.config.from_object('app_config.Config')
app.config['APP_NAME'] = __app_name__
app.config['APP_VERSION'] = __version__
app.config['HEXDIGEST'] = hexdigest

# Logging
logging.basicConfig(
    format=app.config['LOG_FORMAT'],
    datefmt=app.config['LOG_FORMAT_DATE'],
    level=logging.DEBUG
)

# Redis available via app.redis
app.redis = Redis.from_url(app.config['REDIS_URL'])

# Mongo available via applmongo
client = MongoClient(
    app.config['MONGO_HOST'],
    username=app.config['MONGO_USER'],
    password=app.config['MONGO_PASS']
)
app.mongo = client[app.config['MONGODB_DATABASE']]


# a bunch of possibly worthless log-spam
ver = app.config['VER']
app.logger.info('======================================')
app.logger.info(
    f'starting { __app_name__ } { __version__ }'
)
app.logger.info('by @jthop <jh@mode14.com>')
app.logger.info('--------------------------------------')
app.logger.info(f'blake2b source hash { hexdigest }')
app.logger.info(f'imported app_config v{ app_config.__version__ }')
app.logger.info(f'imported services v{ services.__version__ }')
app.logger.info(f'imported notification v{ notification.__version__ }')
app.logger.info('--------------------------------------')
app.logger.info(f'redis module v{ ver["redis_version"] }')
app.logger.info(f'pymongo module v{ ver["pymongo_version"] }')
app.logger.info('--------------------------------------')
app.logger.info(f'python v{ ver["python_version"] }')
app.logger.info(f'environment: pip v{ ver["pip_version"] }')
app.logger.info(f'flask v{ ver["flask_version"] }')
app.logger.info(f'wsgi: { ver["server_software"] }')
app.logger.info(f'docker host: { app.config["DOCKER_HOSTNAME"] }')
app.logger.info('======================================')


############################################


@app.template_filter('fmt_timestamp')
def fmt_timestamp(ts=None):
    """
    Jinja filter to format date/time from timestamp.
    """

    if ts is None:
        return 'no-timestamp'
    dt = datetime.fromtimestamp(int(ts))
    pretty_time = dt.strftime('%m/%d/%y %I:%M %p')
    return pretty_time


@app.errorhandler(404)
def errorhandler_404(e):
    """
    basic 404 handler
    """

    app.logger.info(f'serving 404 for: {request.path}')
    return render_template("404.html")


@app.errorhandler(500)
def errorhandler_500(e):
    """
    basic error handler
    """

    app.logger.error(f'serving 500 for: {request.path}')
    h = f'{e.code} - {e.description}'
    d = e.description
    return render_template(
        'error.html',
        headline=h,
        description=d)


@app.route("/")
def index():
    """
    Handler for the main page.  This displays the cached
    (hopefully) results.
    """

    p = Pinger.load()
    i = services.Incident.fetch()
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
    for s in p.services:
        s.check()

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
    This method is intended for debugging.
    """

    app.redis.flushall()
    return '<html>clear complete</html>'


@app.route("/_clear/mongo")
def clear_all_mongo():
    """
    Endpoint to initiate the deletion of all Mongo documents.
    """

    m = services.Incident()
    if m.cler_all():
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

        svcs = p.services
        serialized = []
        for svc in svcs:
            txt = svc.to_dict()
            serialized.append(txt)

        # mongo
        m = []
        cursor = services.Incident().fetch()
        for row in cursor:
            i = {
                '_id': str(row['_id']),
                'alive': str(row['alive']),
                'response': str(row['response']),
                'timestamp': str(row['timestamp']),
            }
            m.append(i)
        pinger = {
            'version': __version__,
            'created': p.created,
            'updated': p.updated,
            'services': serialized,
            'mongo': m
        }
        return pinger, 200   # will be returned with jsonify
    else:
        h = 'Error dumping'
        d = 'Error finding cazche or creating obj via file'
        return render_template(
            'error.html',
            status_code=400,
            headline=h,
            description=d
        )


#################################
#                               #
#         Pinger                #
#                               #
#################################

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

        services = app.config['YAML'].services
        self.updated = datetime.now()
        self.created = datetime.now()
        self._services = []
        for svc in services:
            app.logger.debug('loading: {}-{}'.format(
                svc.get('name'), svc.get('service_type')))

            module = importlib.import_module('services')
            klass_name = svc.get('service_type').upper()
            klass = getattr(module, klass_name)
            instance = klass(**svc)

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
        for s in self._services:
            if not s.is_alive:
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
        app.redis.set(app.config['YAML'].url, self.serialize())

    @classmethod
    def load(cls):
        """
        Attempt to fetch results from cache.
        If cache is a MISS, load the initial
        data from file.
        """

        cache = app.redis.get(app.config['YAML'].url)
        if cache:
            # Load from CACHE
            app.logger.info('cache HIT! Loading from cache.')
            return pickle.loads(cache)
        else:
            # Load from FILE
            app.logger.info('cache MISS. Loading from file.')
            p = Pinger()
            return p


############################################


if __name__ == '__main__':
    app.run(debug=True)
