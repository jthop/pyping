#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import os
from uuid import uuid4
from datetime import datetime
from flask import current_app as app

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute
from pynamodb.attributes import NumberAttribute
from pynamodb.attributes import UnicodeSetAttribute
from pynamodb.attributes import UTCDateTimeAttribute
from pynamodb.attributes import VersionAttribute

from pynamodb_attributes import UUIDAttribute

unique_key = 'incidents-local'

class Incident(Model):
    class Meta:
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        region = os.environ.get('AWS_DEFAULT_REGION')
        write_capacity_units = 2
        read_capacity_units = 2
        table_name = 'pyping-local'
        __version__ = '1.0'

    __id__ = UUIDAttribute(hash_key=True, default=uuid4())
    __created_at__ = UTCDateTimeAttribute(range_key=True, default=datetime.now)
    __version__ = UnicodeAttribute(null=True, default=Meta.__version__)
    __writes__ = VersionAttribute()
    reason = UnicodeSetAttribute(null=True)
    start = NumberAttribute(null=True)
    stop = NumberAttribute(null=True)
    n = NumberAttribute(null=True)
    name = UnicodeSetAttribute(null=True)

if not Incident.exists():
    Incident.create_table(wait=True)
