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
import pickle
import importlib
import time
from datetime import datetime

from flask import Flask, request, render_template, jsonify
from pymongo import MongoClient
import redis

import config as cfg
import service
import notification

############################################

__name__ = 'pyping'
__version__ = '0.7.2-beta'
__build__ = 103


SERVICE_VERSION = service.__version__
NOTIFICATION_VERSION = notification.__version__
CFG_VERSION = cfg.__version__

PIP_VERSION = os.environ.get('PYTHON_PIP_VERSION', '1.0')
PYTHON_VERSION = os.environ.get('PYTHON_VERSION', '1.0')
DOCKER_HOSTNAME = os.environ.get('HOSTNAME', 'NO_HOSTNAME')
SERVER_SOFTWARE = os.environ.get('SERVER_SOFTWARE', 'server/1.0')
SERVER_VERSION = SERVER_SOFTWARE.split('/')[1]
FLASK_VERSION = pkg_resources.get_distribution("flask").version
PYMONGO_VERSION = pkg_resources.get_distribution("pymongo").version
REDIS_VERSION = pkg_resources.get_distribution("redis").version

############################################

r = redis.StrictRedis(host=cfg.REDIS_HOST)
app = Flask(__name__)

logging.basicConfig(    
     format=cfg.LOG_FORMAT, 
     datefmt=cfg.LOG_FORMAT_DATE, 
     level=logging.DEBUG
     )
logger=app.logger

app.config.update(
    SECRET_KEY=cfg.FLASK_SECRET,
    TEMPLATES_AUTO_RELOAD = True,
    JSONIFY_PRETTYPRINT_REGULAR = True,
     
    APP_NAME = __name__,
    APP_VERSION =__version__,
    APP_BUILD = __build__,
    PYTHON_VERSION = PYTHON_VERSION,
    DOCKER_HOSTNAME = DOCKER_HOSTNAME
    )

logger.info('----------------------------------------')
logger.info(f'starting {__name__} v {__version__} build {__build__}')
logger.info(f'imported cfg v {CFG_VERSION}')
logger.info(f'imported service v {SERVICE_VERSION}')
logger.info(f'imported notification v {NOTIFICATION_VERSION}')
logger.info('----------------------------------------')
logger.info(f'micro-framework: flask v {FLASK_VERSION}')
logger.info(f'interpreter: python v {PYTHON_VERSION}')
logger.info(f'environment prep: pip v {PIP_VERSION}')
logger.info(f'wsgi middleman: {SERVER_SOFTWARE}')
logger.info(f'docker host {DOCKER_HOSTNAME}')
logger.info('----------------------------------------')
logger.info(f'pymongo library v {PYMONGO_VERSION}')
logger.info(f'redis library v {REDIS_VERSION}')
logger.info('----------------------------------------')



############################################



@app.route("/")
def index():
  """Handler for main page"""  
  p = Pinger.load()
  i = Mongo().fetch()  
  return render_template('index.html', pinger=p, incidents=i)


@app.route("/_cron")
def cron():
  p = Pinger.load()
  for service in p.services:
    service.check()
    if service.is_alive:
      # Service is UP
      if service.get_n() > 2:
        # back up - we should write incident to mongodb
        m = Mongo()
        m.insert(service.freeze)
        #send backup notifications
        body = '{} is BACK UP after {} pings.'.format(
          service.pretty_name, 
          service.get_n())
        msg = notification.Notification(
          service.pretty_name, 
          body)
        msg.send()
      service.reset_n() # n=0
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
          service.response)
        msg = notification.Notification(
          service.pretty_name, 
          body)
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

  logger.info(f'HEALTHCHECK for: <{patient}> returned 200')
  return {'success': True}, 200    # will be returned with jsonify


@app.errorhandler(404)
def not_found(e):
  return render_template("404.html")


@app.route("/_test")
def tester():  
  msg = notification.Notification('test sub', 'test body')
  msg.send()
  return '<html>test complete</html>'


@app.route("/_clear/redis")
def clear_all_redis():
  if Pinger.clear():
    return '<html>clear complete</html>'


@app.route("/_clear/mongo")
def clear_all_mongo():
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
  return str(os.environ)


@app.route("/_dump")
def dump_pinger():
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

@app.template_filter('ctime')
def timectime(s):
  return time.ctime(s) # datetime.datetime.fromtimestamp(s)


class Mongo:
  def __init__(self):
    client = MongoClient(
      cfg.MONGO_HOST, 
      username=cfg.MONGO_USER, 
      password=cfg.MONGO_PASS,
    )
    self.db = client[cfg.MONGODB_DATABASE]
    self.collection = self.db['incidents']
    #client.admin.authenticate(MONGO_USER, MONGO_PASS)
    logger.debug('ATTENTION! Mongo class instantiated.')

  def insert(self, data):
    _id = self.collection.insert_one(data)
    logger.debug('Mongo insert of {}.'.format(data))
    return _id

  def fetch(self, x=cfg.DEFAULT_MONGO_ROWS):
    cursor = self.collection.find().sort('now',-1).limit(x)
    logger.debug('Mongo fetch')
    return cursor

  def clear_all(self):
    try:
      cursor = self.collection.find({})
      self.collection.drop()
      logger.debug('Mongo dropped entire collection')
    except Exception as e:
      logger.error(str(e))
      return False
    else:
      return True


class Pinger:  
  """ 
  Funny Pinger objecct we can cache in redis so the website
  can run without having to do it's own checks.
  """

  def __init__(self):
    services = cfg.yaml.services
    epoch = datetime.utcfromtimestamp(0)
    self.updated = epoch
    self.created = epoch
    self._services = []
    for svc in services:
      logger.debug('loading: {}-{}'.format(
        svc.get('name'), svc.get('service_type')))
      """ we want to instantiate a class here, but using a 
      string because the class we'll use is dynamic """
      module = importlib.import_module('service')
      class_name = svc.get('service_type').upper()
      dynClass_ = getattr(module, class_name)
      """copy the dict and pop unneeded vals"""
      shallow_copy = svc.copy()
      shallow_copy.pop('service_type', None)
      s = dynClass_(**shallow_copy)
      self._services.append(s)

  @property  
  def services(self):
    return self._services
  
  @property
  def all_alive(self):
    logger.debug('Someone wants to know if all are ALIVE')
    for service in self._services:
      if not service.is_alive:
        return False   
    return True
  
  @property  
  def all_dead(self):
    logger.debug('Someone wants to know if all are DEAD')
    for service in self._services:
      if service.is_alive:
        return False   
    return True
  
  @property  
  def long_ago(self):
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
    return pickle.dumps(self)
    
  def save(self):
    logger.info('SAVING cache now!')
    self.updated = datetime.now()
    r.set(cfg.yaml.get('url'), self.serialize())
  
  @classmethod
  def load(cls):
    cache = r.get(cfg.yaml.get('url'))
    if cache:
      # Load from CACHE
      logger.info('cache HIT! Loading from cache.')
      return pickle.loads(cache)
    else:
      # Load from FILE
      logger.info('cache MISS. Loading from file.')
      p = Pinger()
      return p

  @classmethod
  def clear(cls):
    r.delete(cfg.yaml.get('url'))
    return True


############################################