import argparse
import binascii
import sys
import time
import threading
from random import randint

from scapy.all import (
    BOOTP,
    DHCP,
    DUID_LL,
    IP,
    UDP,
    Ether,
    conf,
    get_if_addr,
    get_if_hwaddr,
    get_if_raw_hwaddr,
    send,
    sendp,
    sniff,
)

__version__ = '1.0.0'


DEBUG = False
TIMEOUT = 5
IFACE = None
CLIENT_ID = 'aa:bb:cc:dd:ee:ff'

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3


def mac_str_to_bytes(mac):
    """Converts string representation of a MAC address to bytes"""
    if isinstance(mac, bytes):
        return mac
    if not isinstance(mac, str):
        raise TypeError('MAC address given must be a string')
    mac = mac.replace(':', '').replace('-', '').replace('.', '')
    return binascii.unhexlify(mac)


def sniffer(dhcp_client):
    """Starts scapy sniffer and stops when a timeout is reached or a valid packet"""
    def show_packet(x):
        if DEBUG:
            x.summary()
    sniff(
        prn=show_packet,
        timeout=TIMEOUT,
        stop_filter=dhcp_client.is_matching_reply,
    )


class DHCPClient:
    def __init__(self):
        self.xid = randint(0, (2 ** 24) - 1)  # BOOTP 4 bytes, DHCPv6 3 bytes
        self.request = None
        self.reply = None
        self.sniffer = None
        self.offered_address = None

    def craft_request(self, *args, **kwargs):
        self.request = self.craft_discover(*args, **kwargs)
        if DEBUG:
            print(self.request.show())
        return self.request

    def send(self):
        # sending to local link, need to set Ethernet ourselves
        sendp(
            Ether(dst=self._get_ether_dst()) / self.request, verbose=DEBUG
        )

    def sniff_start(self):
        """Starts listening for packets in a new thread"""
        self.sniffer = threading.Thread(target=sniffer, args=[self])
        self.sniffer.start()

    def sniff_stop(self):
        """Waits for sniffer thread to finish"""
        self.sniffer.join()

    def is_matching_reply(self, reply):
        """Checks that we got reply packet"""
        if self.is_offer_type(reply):
            self.reply = reply
            if DEBUG:
                print(reply.show())
            self.offered_address = self.get_offered_address()
            return True
        return False

    def is_offer_type(self, packet):
        raise NotImplementedError

    def get_offered_address(self):
        raise NotImplementedError

    def _get_ether_dst(self):
        raise NotImplementedError


class DHCPv4Client(DHCPClient):
    MAC_BROADCAST = 'FF:FF:FF:FF:FF:FF'

    def craft_discover(self, hw=None):
        """Generates a DHCPDICSOVER packet"""
        if not hw:
            _, hw = get_if_raw_hwaddr(conf.iface)
        else:
            hw = mac_str_to_bytes(hw)
        dhcp_discover = (
            IP(src="0.0.0.0", dst="255.255.255.255")
            / UDP(sport=68, dport=67)
            / BOOTP(chaddr=hw, xid=self.xid, flags=0x8000)
            / DHCP(options=[("message-type", "discover"), "end"])
        )
        # TODO: param req list
        if DEBUG:
            print(dhcp_discover.show())
        return dhcp_discover

    def is_offer_type(self, packet):
        """Checks that packet is a valid DHCP reply"""
        if not packet.haslayer(BOOTP):
            return False
        if packet[BOOTP].op != 2:
            return False
        if packet[BOOTP].xid != self.xid:
            return False
        if not packet.haslayer(DHCP):
            return False
        req_type = [x[1] for x in packet[DHCP].options if x[0] == 'message-type'][0]
        if req_type in [2]:
            return True
        return False

    def get_offered_address(self):
        return self.reply[BOOTP].yiaddr

    def _get_ether_dst(self):
        return self.MAC_BROADCAST


    def go(self, mac=CLIENT_ID):
      self.craft_request(hw=mac)
      self.sniff_start()
      ts = time.time()
      self.send()
      self.sniff_stop()
      te = time.time()

      if self.reply:
        response = 'offered {} in {}ms'.format(
          self.offered_address, round(te-ts, 3))
        results = {
          'alive': True,
          'response': response,
        }
        return results
      else:
        results = { 'alive': False, 'response': 'no dhcp offered'}

