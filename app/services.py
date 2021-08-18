#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import time
import socket
import subprocess
import requests
import ntplib
from flask import current_app as app

import notification
import models

# from icmplib import ping, multiping, traceroute, resolve, Host, Hop

__version__ = '1.2'


#################################
#                               #
#         Incident              #
#                               #
#################################


class Incident:
    __version__ = '2.0'

    def __init__(self, freeze):
        """
        Constructor

        p = {
          'timestamp': int(time.time()),
          'alive': self.is_alive,
          'n': self.last_n,
          'name': self.name,
          'pretty_name': self.pretty_name,
          'response': self.response,
        }

        """

        self.start = time.time()
        self.response = freeze['response']
        self.name = freeze['name']
        self.pretty_name = freeze['pretty_name']
        self._n = 1

        app.logger.debug(f'Just went down: {self.name}')


    def fail(self):
        """
        another failed ping
        """

        self._n += 1
        if self._n == 2:
            self.send_down_msg()

    def retire(self, freeze):
        """
        Service is back online - Persist incident in db, send msg
        Once complete the caller will delete this incident

        parameter: freeze - unused for now, ultimately we should look at
        persisting both obj.freezes
        """

        if self.n > 2:
            app.logger.debug(f'Back up: {self.name}')

            self.stop = time.time()
            self.msg = f'{self.name} came back up after it was down for {self.n} pings. ({self.response })'

            self._id = self.insert_into_db()
            self.send_up_msg()
        return
        
    def insert_into_db(self):
        """
        run the code to insert the data to the db after we format it
        """

        ds = models.Incident(
            start=self.start,
            stop=self.stop,
            response=self.response,
            n=self._n,
            name=self.name
        )
        ds.save()

        app.logger.debug(f'dynamodb insert of {ds.__id__}.')
        return ds.__id__

    def send_down_msg(self):
        # now send msg
        body = f'{self.pretty_name} just went down. {self.response}'
        msg = notification.Notification(self.pretty_name, body)
        try:
            msg.send()
        except Exception as e:
            app.logger.error(e)

    def send_up_msg(self):
        # send backup notifications
        msg = notification.Notification(self.name, self.msg)
        try:
            msg.send()
        except Exception as e:
            app.logger.error(e)

    @property
    def n(self):
        return self._n


###################################
#                                 #
#         Base Class              #
#                                 #
###################################


class Service(object):
    """
    Our base class for all checks.
    Implements parts of the check() method.
    """

    def __init__(self, name):
        # constructor - called by child class
        self.name = name

        self.n = 0
        self.last_n = 0
        self.alive = True

        # initialize this empty strings
        self.response = ''

        # all svcs can use the default timeout from config
        self.timeout = app.config['TIMEOUT']

        """
        use this attribute to save incidents after 'just down'.
        that way we can easily recall the incidents when the
        corresponding 'just up' event happens.
        """
        self.incident = None

    @property
    def is_alive(self):
        # true/false is the service dead

        if self.incident:
            return False
        return True

    @property
    def pretty_name(self):
        # keep these consistent - used for www and notifications
        return '{} [{}]'.format(self.name, self.description)

    @property
    def freeze(self):
        # used as the model to write to mongo
        p = {
          'timestamp': int(time.time()),
          'alive': self.is_alive,
          'n': self.last_n,
          'name': self.name,
          'pretty_name': self.pretty_name,
          'response': self.response,
        }
        return p

    def timer_start(self):
        # little helper for timing service checks
        # self.start_ms = self.get_ms
        self.start_ms = time.monotonic() * 1000

    def timer_stop(self):
        # little helper for timing service checks
        stop_ms = time.monotonic() * 1000
        elapsed_ms = stop_ms - self.start_ms
        r = 'elapsed_ms = {:.2f}'.format(elapsed_ms)
        return r

    def set_dead(self):
        """
        This method sets the service .alive attribute to False.
        This is run every check() that fails, even if the service
        was already dead.  This makes it a prime location to check
        for service.n = 2 to trigger notifications.
        """

        if self.incident is None:
            # we probably just went down
            self.incident = Incident(self.freeze)
        else:
            """
            well if we already have an incident obj we must just be on
            another failed ping
            """
            self.incident.fail()

    def set_alive(self):
        """
        This method sets the service .alive attribute to True.
        When a service is dead, This is the best spot to reset
        service.n back to 0.
        """

        if self.incident is not None:
            # Wow we were in an incident, we must be 'just up'
            self.incident.retire(self.freeze)

            # not sure why I had this but finished isn't set anywhere
            # if self.incident.finished:
            del self.incident
            self.incident = None

    def check(self):
        """
        This is it right here, what we are all here for.  The
        check method determines if we are up or down.
        """

        try:
            app.logger.debug('running check for {}.'.format(self.name))
            # this is where service specific checks begin
            self.response = self._check()
        except Exception as e:
            app.logger.error(
                'Error - Service Down - {}@{}'.format(self.name, e))
            self.response = str(e)
            self.set_dead()
            return False
        else:
            app.logger.info(
                '{} check complete.  Service UP!'.format(self.name))
            app.logger.debug('Up! {}@{}'.format(self.response, self.name))
            self.set_alive()
            return True

    def to_dict(self):
        """
        @params - none - initially run by child class to_dict()

        @return - dict() - the dict returned will then have more
        site specific data added by child class
        """

        d = {
          'name': self.name,
          'alive': self.is_alive,
          'n': self.n,
          'last_n': self.last_n,
          'timeout': self.timeout,
          'response': self.response
        }
        return d


class TCP(Service):
    """
    TCP checker.  Throws exception if tcp socket is not opened
    before the timeout.
    """

    def __init__(self, **kwargs):
        # This init runs first, then the base class init is called via super()
        name = kwargs['name']
        ip = kwargs['ip']
        port = kwargs['port']

        super().__init__(name)
        self.ip = ip
        self.port = port

    @property
    def description(self):
        return 'tcp://{}:{}'.format(self.ip, self.port)

    def _check(self):
        self.timer_start()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.ip, self.port))
        s.close()
        r = self.timer_stop()
        return 'elapsed time {}'.format(r)

    def to_dict(self):
        d = super().to_dict()
        d['service_type'] = 'tcp'
        d['ip'] = self.ip
        d['port'] = self.port
        return d


# class ICMP2(Service):
#     """
#     ICMP Ping - tell if a host is alive
#     On some Linux systems, you must allow this feature:
#
#     $ echo 'net.ipv4.ping_group_range = 0 2147483647' | sudo
#         tee -a /etc/sysctl.conf
#     $ sudo sysctl -p
#     You can check the current value with the following command:
#
#     $ sysctl net.ipv4.ping_group_range
#     net.ipv4.ping_group_range = 0 2147483647
#     """
#
#     def __init__(self, **kwargs):
#         """ This constructor will run first """
#         super().__init__(name)
#         self.ip = ip
#
#     @property
#     def description(self):
#         return 'icmp://{}'.format(self.ip)
#
#     def _check(self):
#         host = ping(self.ip, timeout=self.timeout, privileged=False)
#         if not host.is_alive:
#             raise Exception('ICMP host is not alive')
#         elapsed_ms = host.avg_rtt
#         self.info = 'avg rtt {}'.format(elapsed_ms)
#         return


class ICMP(Service):
    """
    ICMP checker.  Python must be run as root to open true ICMP socket
    so this runs the ping binary via shell.
    """

    def __init__(self, **kwargs):
        # This init runs first, then the base class init is called via super()
        name = kwargs['name']
        ip = kwargs['ip']

        super().__init__(name)
        self.ip = ip

    @property
    def description(self):
        return 'icmp://{}'.format(self.ip)

    def _check(self):
        alive, response = self.ping()
        if not alive:
            if response:
                raise Exception(response)
            else:
                raise Exception('ICMP host is not alive')
        return str(response)

    def ping(self):
        command = ['ping', '-c', '1', self.ip]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            output = result.stdout.splitlines()
            return True, output
        else:
            output = result.stderr.splitlines()
            return False, output

    def to_dict(self):
        d = super().to_dict()
        d['service_type'] = 'icmp'
        d['ip'] = self.ip
        return d


class HTTP(Service):
    """
    URL checker.  Uses python requests to attempt to open up the
    specified URL.  Also makes sure the server returns a 200 status.
    """

    def __init__(self, **kwargs):
        # This init runs first, then the base class init is called via super()
        name = kwargs['name']
        url = kwargs['url']

        super().__init__(name)
        self.url = url

    @property
    def description(self):
        return self.url

    def _check(self):
        response = requests.get(self.url)
        status = response.status_code
        if status != 200:
            raise Exception(
              'Expected status code 200 but received {}'.format(status))
        return 'status-code: {}'.format(status)

    def to_dict(self):
        d = super().to_dict()
        d['service_type'] = 'http'
        d['url'] = self.url
        return d


class NTP(Service):
    """
    NTP Checker.  Simple checker using pythong NTP lib.  Makes sure the NTP
    server is alive, as well as looking at the clock offset.
    """

    def __init__(self, **kwargs):
        # This init runs first, then the base class init is called via super()
        name = kwargs['name']
        ip = kwargs['ip']

        super().__init__(name)
        self.ip = ip

    @property
    def description(self):
        return 'ntp://{}'.format(self.ip)

    def _check(self):
        client = ntplib.NTPClient()
        # next line will throw the exception
        response = client.request(self.ip)
        offset = 'offset = {:.2f}'.format(response.offset)
        return offset

    def to_dict(self):
        d = super().to_dict()
        d['service_type'] = 'ntp'
        d['ip'] = self.ip
        return d


class DHCP(Service):
    """
    DHCP Checker.  This uses a remote agent to atttempt to get a DHCP address
    offered.  Agent is intended for future expansion.
    """

    def __init__(self, **kwargs):
        # This init runs first, then the base class init is called via super()
        name = kwargs['name']
        url = kwargs['url']
        mac = kwargs.get('mac')

        super().__init__(name)
        if mac and app.config['MAC_PLACEHOLDER'] in url:
            self.url = url.replace(app.config['MAC_PLACEHOLDER'], mac)
        self.mac = mac

    @property
    def description(self):
        mac = getattr(self, 'mac', 'No MAC specified')
        return mac

    def _check(self):
        try:
            r = requests.get(self.url)
            alive = r.json().get('alive')
        except Exception as e:
            app.logger.error(f'DHCP check error: {str(e)}')
            raise Exception('error in initial agent communications')

        if alive:
            app.logger.debug('DHCP is alive.')
            response = r.json().get('response', 'NO response')
            return response
        else:
            raise Exception('Remote machine determined that DHCP \
            has failed the check.')

    def to_dict(self):
        d = super().to_dict()
        d['service_type'] = 'dhcp'
        d['url'] = self.url
        d['mac'] = self.mac or 'None'
        return d
