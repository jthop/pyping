#!/usr/bin/env python3
#---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import logging
import smtplib
from email.message import EmailMessage

import config as cfg
from twilio.rest import Client

__version__ = '1.3'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

############################################


class Notification:
    def __init__(self, subject, body):
        logger.debug('Beginning Notification class init')
        # Read in our subscribers
        logger.debug('reading in subscribers')
        self.subscribers = cfg.yaml.get('subscribers', [])
        self.transports = []

        for sub in self.subscribers:
            logger.debug('Constructing notification for {}@{}'.format(
              sub.destination, sub.transport))
            if sub.transport.lower() == 'email':
                transport = Email(subject, body, sub)
            elif sub.transport.lower() == 'twilio-sms':
                transport = Twilio(subject, body, sub)
            self.transports.append(transport)

    def send(self):
        """ Sends to all subscribers via all transports """
        if not cfg.SEND_NOTIFICATIONS:
            return False
        for transport in self.transports:
            transport._send()


class Email:
    def __init__(self, subject, body, sub):
        # Setup email config
        logger.debug('reading in smtp config')
        self.smtp_host = cfg.yaml.get('smtp_host', None)
        if self.smtp_host:
            self.smtp_port = cfg.yaml.get('smtp_port', 25)
            self.smtp_user = cfg.yaml.get('smtp_user', None)
            if self.smtp_user:
                self.smtp_pass = cfg.yaml.get('smtp_pass', '')
            self.return_email = cfg.yaml.get('return_email', 'you_forgot@config-return-email.oops')
            self.subject = subject
            self.body = body
            self.sub = sub

    def _send(self):
        """ Sends via email """
        logger.info('Sending notification via email for {}'.format(self.sub.destination))
        msg = EmailMessage()
        msg['Subject'] = self.subject
        msg['From'] = self.return_email
        msg['To'] = self.sub.destination
        msg.set_content(self.body)

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            if self.smtp_user:
                server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)
            return server


class Twilio:
    def __init__(self, subject, body, sub):
        ## Setup Twilio config
        logger.debug('reading in twilio config')
        self.twilio_account_sid = cfg.yaml.get('twilio_account_sid', None)
        if self.twilio_account_sid:
            self.twilio_auth_token = cfg.yaml.get('twilio_auth_token', '')
            self.twilio_messaging_service_sid = cfg.yaml.get('twilio_messaging_service_sid', '')
            self.body = body
            self.sub = sub

    def _send(self):
        """ Sends via Twilio """
        logger.info('Sending notification via twilio for {}'.format(self.sub.destination))
        client = Client(self.twilio_account_sid, self.twilio_auth_token)
        message = client.messages.create(
          body=self.body,
          messaging_service_sid=self.twilio_messaging_service_sid,
          to=self.sub.destination)
        return message.sid
