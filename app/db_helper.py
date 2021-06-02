#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

from pymongo import MongoClient
from flask import current_app as app


__version__ = '1.3'


############################################


class Mongo:
    def __init__(self):
        """
        Constructor, mainly sets up Mongo
        connection.
        """

        client = MongoClient(
          app.config['MONGO_HOST'],
          username=app.config['MONGO_USER'],
          password=app.config['MONGO_PASS']
        )
        self.db = client[app.config['MONGODB_DATABASE']]
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

    def fetch(self, x=None):
        """
        Fetch most recent 10 rows for homepage.
        """

        # this is a weird fix for app.config not available at import
        if x is None:
            x = app.config['DEFAULT_MONGO_ROWS']

        cursor = self.collection.find().sort('timestamp', -1).limit(x)
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
