#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# This software is in the public domain, furnished "as is", without technical
# support, and with no warranty, express or implied, as to its usefulness for
# any purpose.
#
#  Author: Jamie Hopper <jh@mode14.com>
# --------------------------------------------------------------------------

import smtplib
from email.message import EmailMessage
from flask import current_app as app
from twilio.rest import Client


__version__ = '1.5'


############################################


class Notification:
    def __init__(self, subject, body):
        app.logger.debug('Beginning Notification class init')
        # Read in our subscribers
        app.logger.debug('reading in subscribers')
        self.subscribers = app.config['YAML'].get('subscribers', [])
        self.transports = []

        for sub in self.subscribers:
            app.logger.debug('Constructing notification for {}@{}'.format(
              sub.destination, sub.transport))
            if sub.transport.lower() == 'email':
                transport = Email(subject, body, sub)
            elif sub.transport.lower() == 'twilio-sms':
                transport = Twilio(subject, body, sub)
            self.transports.append(transport)

    def send(self):
        """ Sends to all subscribers via all transports """
        if not app.config['SEND_NOTIFICATIONS']:
            return False
        for transport in self.transports:
            transport._send()


class Email:
    def __init__(self, subject, body, sub):
        # Setup email config
        app.logger.debug('reading in smtp config')
        self.smtp_host = app.config['YAML'].get('smtp_host', None)
        if self.smtp_host:
            self.smtp_port = app.config['YAML'].get('smtp_port', 25)
            self.smtp_user = app.config['YAML'].get('smtp_user', None)
            if self.smtp_user:
                self.smtp_pass = app.config['YAML'].get('smtp_pass', '')
            self.return_email = app.config['YAML'].get(
                'return_email',
                'you_forgot@config-return-email.oops'
            )
            self.subject = subject
            self.body = body
            self.sub = sub

    def _send(self):
        """ Sends via email """
        app.logger.info(
            'Sending notification via email for {}'.format(
                self.sub.destination)
            )
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
        # Setup Twilio config
        app.logger.debug('reading in twilio config')
        self.twilio_account_sid = app.config['YAML'].get(
            'twilio_account_sid', None)
        if self.twilio_account_sid:
            self.twilio_auth_token = app.config['YAML'].twilio_auth_token
            self.twilio_messaging_service_sid = app.config['YAML'].twilio_messaging_service_sid
            self.body = body
            self.sub = sub

    def _send(self):
        """ Sends via Twilio """
        app.logger.info(
            'Sending notification via twilio for {}'.format(
                self.sub.destination)
        )
        client = Client(self.twilio_account_sid, self.twilio_auth_token)
        message = client.messages.create(
          body=self.body,
          messaging_service_sid=self.twilio_messaging_service_sid,
          to=self.sub.destination)
        return message.sid
