#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

from uuid import uuid4
from datetime import datetime

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute
from pynamodb.attributes import NumberAttribute
from pynamodb.attributes import UnicodeSetAttribute
from pynamodb.attributes import UTCDateTimeAttribute

from pynamodb_attributes import UUIDAttribute

class Incident(Model):
    class Meta:
        table_name = app.config['YAML'].url  # https://pyping.mode14.net
        __version__ = '1.0'

    __id__ = UUIDAttribute(hash_key=True, default=uuid4())
    __created_at__ = UTCDateTimeAttribute(range_key=True, default=datetime.now)
    __version__ = UnicodeAttribute(null=True, default=Meta.__version__)

    reason = UnicodeSetAttribute(null=True)
    start = NumberAttribute(null=True)
    stop = NumberAttribute(null=True)
    n = NumberAttribute(null=True)
    name = UnicodeSetAttribute(null=True)

if not Incident.exists():
    Incident.create_table(wait=True)
