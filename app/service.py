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
# from icmplib import ping, multiping, traceroute, resolve, Host, Hop
from flask import current_app as app
import config as cfg

__version__ = '1.7'


############################################


class Service(object):
    """
    Our base class for all checks
    """
    def __init__(self, name):
        """ constructor - called by child class """
        self.name = name
        self.n = 0
        self.alive = True
        # initialize this empty strings
        self.response = ''
        # all svcs can use the default timeout from config
        self.timeout = cfg.TIMEOUT

    @property
    def is_alive(self):
        """ true/false is the service dead """
        return self.alive

    @property
    def pretty_name(self):
        """ keep these consistent - used for www and notifications """
        return '{} [{}]'.format(self.name, self.description)

    @property
    def freeze(self):
        """ used as the model to write to mongo  """
        p = {
          'now': self.get_epoch(),
          'alive': self.is_alive,
          'n': self.n,
          'name': self.name,
          'pretty_name': self.pretty_name,
          'response': self.response,
        }
        return p

    def get_epoch(self):
        """ used to store current time """
        return int(time.time())

    def timer_start(self):
        """ little helper for timing service checks """
        # self.start_ms = self.get_ms
        self.start_ms = time.monotonic() * 1000

    def timer_stop(self):
        """ little helper for timing service checks """
        stop_ms = time.monotonic() * 1000
        elapsed_ms = stop_ms - self.start_ms
        r = 'elapsed_ms = {:.2f}'.format(elapsed_ms)
        return r

    def get_n(self):
        """ getter for n """
        return self.n

    def incr_n(self):
        """ increment n """
        self.n += 1
        return True

    def reset_n(self):
        """ n back to 0 """
        self.n = 0
        return True

    def set_dead(self):
        """ Set self.alive to false """
        self.alive = False
        return True

    def set_alive(self):
        """ Set self.alive to true """
        self.alive = True
        return True

    def check(self):
        """ here is the base of the check"""
        try:
            app.logger.debug('running check for {}.'.format(self.name))
            # this is where service specific checks begin
            self.response = self._check()
        except Exception as e:
            app.logger.error('Error! {}@{}'.format(self.name, e))
            self.response = str(e)
            self.set_dead()
        else:
            app.logger.info(
                '{} check complete.  Service UP!'.format(self.name))
            app.logger.debug('Up! {}@{}'.format(self.response, self.name))
            self.set_alive()

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
          'timeout': self.timeout,
          'response': self.response
        }
        return d


class TCP(Service):
    """ Child class of Service with service specific implementations """
    def __init__(self, name, ip, port):
        """ This constructor will run first """
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
#     def __init__(self, name, ip):
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
    """ Child class of Service with service specific implementations """
    def __init__(self, name, ip):
        """ This constructor will run first """
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
    """ Child class of Service with service specific implementations """
    def __init__(self, name, url):
        """ This constructor will run first """
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
    """ Child class of Service with service specific implementations """
    def __init__(self, name, ip):
        """ This constructor will run first """
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
    """ Child class of Service with service specific implementations """
    def __init__(self, name, url, mac=None):
        """ This constructor will run first """
        super().__init__(name)

        if mac and cfg.MAC_PLACEHOLDER in url:
            self.url = url.replace(cfg.MAC_PLACEHOLDER, mac)
        self.mac = mac

    @property
    def description(self):
        mac = getattr(self, 'mac', 'No MAC specified')
        return mac

    def _check(self):
        r = requests.get(self.url)
        alive = r.json().get('alive')
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
